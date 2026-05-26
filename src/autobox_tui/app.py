"""autobox agents — session manager TUI."""

from __future__ import annotations

import os
import shutil
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
    get_container_exit_code,
    get_project_dir,
    list_agents,
    restore_gitfile,
    slugify,
    stop_agent,
)

TMUX_SESSION = "claude"
THEME_FILE = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "autobox",
    "theme",
)

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


class AgentListView(ListView):
    """ListView that auto-selects the first item on focus."""

    def on_focus(self) -> None:
        if self.index is None and self.children:
            self.index = 0


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

        pad = max(36 - len(a.name), 1)
        yield Static(
            f"  [bold]{a.name}[/bold]"
            f"{'':>{pad}}"
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

    .section-label {
        padding: 1 2 0 2;
        color: $text-muted;
    }

    .agent-list {
        height: auto;
        max-height: 50%;
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
        Binding("t", "toggle_theme", "Theme"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("escape", "focus_prompt", show=False),
    ]

    project_dir: var[str] = var("")
    agents: var[list[Agent]] = var(list)
    attach_container: str = ""
    enter_worktree: str = ""
    focus_agents: bool = False

    def compose(self) -> ComposeResult:
        yield Static("", id="header")
        with Vertical(id="prompt-container"):
            yield Input(placeholder="Start new agent with a task...", id="prompt")
        yield Label(" Working", classes="section-label", id="working-label")
        yield AgentListView(id="working-list", classes="agent-list")
        yield Label(" Completed", classes="section-label", id="completed-label")
        yield AgentListView(id="completed-list", classes="agent-list")
        yield Static(
            "No agents yet — type a task above to start one.",
            id="empty-state",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(THEME_DARK)
        self.register_theme(THEME_LIGHT)

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

        if self.focus_agents:
            working = self.query_one("#working-list", AgentListView)
            completed = self.query_one("#completed-list", AgentListView)
            if working.display and working.children:
                working.focus()
            elif completed.display and completed.children:
                completed.focus()

    def on_key(self, event: events.Key) -> None:
        prompt = self.query_one("#prompt", Input)
        working = self.query_one("#working-list", AgentListView)
        completed = self.query_one("#completed-list", AgentListView)

        if event.key == "down" and prompt.has_focus:
            if working.display and working.children:
                working.focus()
                working.index = 0
                event.prevent_default()
            elif completed.display and completed.children:
                completed.focus()
                completed.index = 0
                event.prevent_default()
        elif event.key == "up" and completed.has_focus:
            if completed.index is None or completed.index == 0:
                if working.display and working.children:
                    working.focus()
                    working.index = len(working.children) - 1
                else:
                    prompt.focus()
                event.prevent_default()
        elif event.key == "up" and working.has_focus:
            if working.index is None or working.index == 0:
                prompt.focus()
                event.prevent_default()
        elif event.key == "down" and working.has_focus:
            if working.index is not None and working.index >= len(working.children) - 1:
                if completed.display and completed.children:
                    completed.focus()
                    completed.index = 0
                    event.prevent_default()

    def _focused_list(self) -> tuple[ListView, list[Agent]] | None:
        working = self.query_one("#working-list", AgentListView)
        completed = self.query_one("#completed-list", AgentListView)
        running = [a for a in self.agents if a.running]
        done = [a for a in self.agents if not a.running]
        if working.has_focus:
            return working, running
        if completed.has_focus:
            return completed, done
        return None

    def action_toggle_theme(self) -> None:
        self.theme = "autobox-light" if self.theme == "autobox-dark" else "autobox-dark"
        try:
            os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
            with open(THEME_FILE, "w") as f:
                f.write(self.theme)
        except OSError:
            pass

    def _poll_status(self) -> None:
        old_states = {a.name: (a.running, a.container_name) for a in self.agents}
        self.refresh_agents()

        for name, (was_running, container) in old_states.items():
            if not was_running:
                continue
            new_agent = next((a for a in self.agents if a.name == name), None)
            if new_agent and not new_agent.running:
                get_container_exit_code(container)
                cleanup_agent(self.project_dir, new_agent)
                self.refresh_agents()
                self._desktop_notify(f"{name} — done")
                self.bell()

    @staticmethod
    def _desktop_notify(msg: str) -> None:
        notify_bin = shutil.which("notify-send")
        if notify_bin:
            subprocess.Popen(
                [notify_bin, "-a", "autobox", "autobox", msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def refresh_agents(self) -> None:
        new_agents = list_agents(self.project_dir)

        old_key = [(a.name, a.running, a.status_summary) for a in self.agents]
        new_key = [(a.name, a.running, a.status_summary) for a in new_agents]
        if old_key == new_key:
            return

        self.agents = new_agents
        running = [a for a in self.agents if a.running]
        done = [a for a in self.agents if not a.running]

        working_list = self.query_one("#working-list", AgentListView)
        completed_list = self.query_one("#completed-list", AgentListView)

        saved_working = working_list.index
        saved_completed = completed_list.index

        with self.batch_update():
            working_list.clear()
            for agent in running:
                working_list.append(AgentItem(agent))

            completed_list.clear()
            for agent in done:
                completed_list.append(AgentItem(agent))

            if saved_working is not None and saved_working < len(running):
                working_list.index = saved_working
            if saved_completed is not None and saved_completed < len(done):
                completed_list.index = saved_completed

            has_any = bool(self.agents)
            self.query_one("#working-label", Label).display = bool(running)
            working_list.display = bool(running)
            self.query_one("#completed-label", Label).display = bool(done)
            completed_list.display = bool(done)
            self.query_one("#empty-state", Static).display = not has_any

    @on(Input.Submitted, "#prompt")
    def on_prompt_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        name = slugify(text)
        self.spawn_agent(name=name, prompt=text)

    @on(ListView.Selected)
    def on_agent_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, AgentItem):
            agent = event.item.agent
            if agent.running:
                self.attach_container = agent.container_name
                self.exit()
            elif os.path.isdir(agent.path):
                restore_gitfile(self.project_dir, agent)
                self.enter_worktree = agent.path
                self.exit()

    def action_delete(self) -> None:
        focus = self._focused_list()
        if not focus:
            return
        lv, agent_list = focus
        if lv.index is not None and lv.index < len(agent_list):
            agent = agent_list[lv.index]
            if agent.running or agent.status_summary != "clean":
                label = "running" if agent.running else agent.status_summary
                self.push_screen(
                    ConfirmDeleteScreen(agent.name, label),
                    callback=lambda confirmed: self._do_delete(agent) if confirmed else None,
                )
            else:
                self._do_delete(agent)

    def _do_delete(self, agent: Agent) -> None:
        err = delete_agent(self.project_dir, agent)
        if err:
            self.notify(f"Delete failed: {err}", severity="error")
        self.refresh_agents()

    def action_cursor_down(self) -> None:
        focus = self._focused_list()
        if focus:
            focus[0].action_cursor_down()
        else:
            working = self.query_one("#working-list", AgentListView)
            completed = self.query_one("#completed-list", AgentListView)
            if working.display:
                working.focus()
            elif completed.display:
                completed.focus()

    def action_cursor_up(self) -> None:
        focus = self._focused_list()
        if focus:
            focus[0].action_cursor_up()

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
        self.app.call_from_thread(self.refresh_agents)


def main() -> None:
    focus_agents = False
    original_cwd = os.getcwd()
    while True:
        os.chdir(original_cwd)
        app = AgentsApp()
        app.focus_agents = focus_agents
        app.run()
        if app.attach_container:
            result = subprocess.run(
                ["docker", "exec", "-it", app.attach_container,
                 "tmux", "attach", "-t", TMUX_SESSION]
            )
            if result.returncode != 0:
                subprocess.run(
                    ["docker", "attach", "--detach-keys=ctrl-q",
                     app.attach_container]
                )
            focus_agents = True
            continue
        if app.enter_worktree:
            os.chdir(app.enter_worktree)
            subprocess.run(["claude"])
            focus_agents = True
            continue
        break


if __name__ == "__main__":
    main()
