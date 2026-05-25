"""autobox agents — session manager TUI."""

from __future__ import annotations

import os
import subprocess

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import var
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static

from autobox_tui.data import (
    AUTOBOX_BIN,
    Agent,
    cleanup_agent,
    delete_agent,
    get_project_dir,
    list_agents,
    slugify,
    stop_agent,
)

DETACH_KEYS = "ctrl-q"
THEME_FILE = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autobox", "theme")

# NvChad onenord
THEME_DARK = Theme(
    name="autobox-dark",
    primary="#81A1C1",
    secondary="#A3BE8C",
    accent="#B48EAD",
    warning="#EBCB8B",
    error="#d57780",
    success="#A3BE8C",
    foreground="#bfc5d0",
    background="#2a303c",
    surface="#333945",
    panel="#434C5E",
    boost="#4C566A",
    dark=True,
)

# NvChad one_light
THEME_LIGHT = Theme(
    name="autobox-light",
    primary="#4078f2",
    secondary="#50a14f",
    accent="#a626a4",
    warning="#c18401",
    error="#d84a3d",
    success="#50a14f",
    foreground="#383a42",
    background="#fafafa",
    surface="#f4f4f4",
    panel="#e5e5e6",
    boost="#dfdfe0",
    dark=False,
)


class ConfirmDeleteScreen(ModalScreen[bool]):

    CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        border: thick $error;
        background: $surface;
    }
    #confirm-buttons {
        margin-top: 1;
        height: auto;
        align: center middle;
    }
    #confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, agent_name: str, status: str) -> None:
        super().__init__()
        self._agent_name = agent_name
        self._status = status

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(
                f"Delete [bold]{self._agent_name}[/bold]?\n\n"
                f"Uncommitted changes: {self._status}\n"
                f"This cannot be undone.",
                markup=True,
            )
            with Vertical(id="confirm-buttons"):
                yield Button("Delete", variant="error", id="confirm-yes")
                yield Button("Cancel", variant="primary", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


class AgentItem(ListItem):

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        a = self.agent
        status = a.status_summary
        if a.running:
            status_styled = f"[bold $success]● {status}[/]"
        elif status == "clean":
            status_styled = f"[dim]{status}[/dim]"
        else:
            status_styled = f"[$warning]{status}[/]"

        yield Static(
            f"  [bold]{a.name}[/bold]"
            f"{'':>{36 - len(a.name)}}"
            f"{status_styled:>20}"
            f"  [dim]{a.age}[/dim]",
            markup=True,
        )


class AgentsApp(App):

    TITLE = "autobox agents"
    CSS = """
    #header {
        height: 1;
        background: $primary;
        color: $background;
        padding: 0 2;
    }

    #prompt-container {
        height: auto;
        padding: 1 2 0 2;
    }

    #prompt {
        margin: 0;
    }

    #agents-label {
        padding: 1 2 0 2;
        color: $text-muted;
    }

    #agent-list {
        height: 1fr;
        margin: 0 1;
    }

    #empty-state {
        height: 1fr;
        margin: 0 2;
        padding: 2 4;
        color: $text-muted;
        content-align: center middle;
    }

    ListItem {
        height: 1;
        padding: 0;
    }

    ListItem > Static {
        height: 1;
    }

    Footer {
        color: $foreground;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete", "Delete"),
        Binding("s", "stop", "Stop"),
        Binding("t", "toggle_theme", "Theme"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("escape", "focus_prompt", show=False),
    ]

    project_dir: var[str] = var("")
    agents: var[list[Agent]] = var(list)
    attach_container: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="header")
        with Vertical(id="prompt-container"):
            yield Input(placeholder="Start new agent with a task...", id="prompt")
        yield Label(
            " Agents  [dim]Enter=attach  Ctrl-Q=detach[/dim]",
            id="agents-label",
        )
        yield ListView(id="agent-list")
        yield Static(
            "No agents yet — type a task above to start one.",
            id="empty-state",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(THEME_DARK)
        self.register_theme(THEME_LIGHT)

        # Restore saved theme, or detect from system
        saved = None
        try:
            saved = open(THEME_FILE).read().strip()
        except OSError:
            pass

        if saved in ("autobox-dark", "autobox-light"):
            self.theme = saved
        else:
            colorfgbg = os.environ.get("COLORFGBG", "")
            if colorfgbg:
                try:
                    bg = int(colorfgbg.rsplit(";", 1)[-1])
                    self.theme = "autobox-light" if bg >= 8 else "autobox-dark"
                except ValueError:
                    self.theme = "autobox-dark"
            else:
                self.theme = "autobox-dark"

        try:
            self.project_dir = get_project_dir()
        except Exception:
            self.project_dir = os.getcwd()

        short_path = self.project_dir.replace(os.path.expanduser("~"), "~")
        self.query_one("#header", Static).update(f" autobox  ─  {short_path}")
        self.refresh_agents()
        self.set_interval(3.0, self._poll_status)

    def on_key(self, event: events.Key) -> None:
        prompt = self.query_one("#prompt", Input)
        agent_list = self.query_one("#agent-list", ListView)

        if event.key == "down" and prompt.has_focus:
            if agent_list.display and self.agents:
                agent_list.focus()
                event.prevent_default()
        elif event.key == "up" and agent_list.has_focus:
            if agent_list.index is None or agent_list.index == 0:
                prompt.focus()
                event.prevent_default()

    def action_toggle_theme(self) -> None:
        self.theme = "autobox-light" if self.theme == "autobox-dark" else "autobox-dark"
        try:
            os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
            with open(THEME_FILE, "w") as f:
                f.write(self.theme)
        except OSError:
            pass

    def _poll_status(self) -> None:
        old_states = {a.name: a.running for a in self.agents}
        self.refresh_agents()
        new_states = {a.name: a.running for a in self.agents}

        for name, was_running in old_states.items():
            if was_running and not new_states.get(name, False):
                agent = next((a for a in self.agents if a.name == name), None)
                if agent:
                    cleanup_agent(self.project_dir, agent)
                    self.refresh_agents()
                    self.notify(f"{name} finished")

    def refresh_agents(self) -> None:
        self.agents = list_agents(self.project_dir)
        agent_list = self.query_one("#agent-list", ListView)
        agent_list.clear()
        for agent in self.agents:
            agent_list.append(AgentItem(agent))

        has_agents = len(self.agents) > 0
        agent_list.display = has_agents
        self.query_one("#empty-state", Static).display = not has_agents

    @on(Input.Submitted, "#prompt")
    def on_prompt_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        name = slugify(text)
        self.spawn_agent(name=name, prompt=text)

    @on(ListView.Selected, "#agent-list")
    def on_agent_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, AgentItem):
            agent = event.item.agent
            if agent.running:
                self.attach_container = agent.container_name
                self.exit()
            else:
                self.notify(
                    "Agent not running — start a new one from the prompt.",
                    severity="warning",
                )

    def action_delete(self) -> None:
        agent_list = self.query_one("#agent-list", ListView)
        if agent_list.index is not None and agent_list.index < len(self.agents):
            agent = self.agents[agent_list.index]
            if agent.running or agent.status_summary != "clean":
                label = "running" if agent.running else agent.status_summary
                self.push_screen(
                    ConfirmDeleteScreen(agent.name, label),
                    callback=lambda confirmed: self._do_delete(agent) if confirmed else None,
                )
            else:
                self._do_delete(agent)

    def action_stop(self) -> None:
        agent_list = self.query_one("#agent-list", ListView)
        if agent_list.index is not None and agent_list.index < len(self.agents):
            agent = self.agents[agent_list.index]
            if agent.running:
                stop_agent(agent)
                self.notify(f"Stopped {agent.name}")
                self.refresh_agents()

    def _do_delete(self, agent: Agent) -> None:
        err = delete_agent(self.project_dir, agent)
        if err:
            self.notify(f"Delete failed: {err}", severity="error")
        else:
            self.notify(f"Deleted {agent.name}")
        self.refresh_agents()

    def action_cursor_down(self) -> None:
        agent_list = self.query_one("#agent-list", ListView)
        agent_list.focus()
        agent_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        agent_list = self.query_one("#agent-list", ListView)
        agent_list.focus()
        agent_list.action_cursor_up()

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", Input).focus()

    @work(thread=True)
    def spawn_agent(self, name: str, prompt: str) -> None:
        cmd = [AUTOBOX_BIN, "--detach", "--name", name, "--", prompt]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.app.call_from_thread(
                self.notify,
                f"Failed to start: {result.stderr.strip()}",
                severity="error",
            )
        else:
            self.app.call_from_thread(self.notify, f"Started {name}")
        self.app.call_from_thread(self.refresh_agents)


def main() -> None:
    while True:
        app = AgentsApp()
        app.run()
        if app.attach_container:
            subprocess.run(
                ["docker", "attach", f"--detach-keys={DETACH_KEYS}", app.attach_container]
            )
            continue
        break


if __name__ == "__main__":
    main()
