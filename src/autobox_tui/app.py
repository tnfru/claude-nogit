"""autobox agents — session manager TUI."""

from __future__ import annotations

import os
import shutil
import subprocess

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import var
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static

from autobox_tui.data import Agent, delete_agent, get_project_dir, list_agents, slugify

AUTOBOX_BIN = shutil.which("autobox") or "autobox"


class AgentItem(ListItem):
    """A single agent row in the list."""

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        a = self.agent
        status = a.status_summary
        if status == "clean":
            status_styled = f"[dim]{status}[/dim]"
        else:
            status_styled = f"[green]{status}[/green]"

        yield Static(
            f"  [bold]{a.name}[/bold]"
            f"{'':>{40 - len(a.name)}}"
            f"{status_styled:>16}"
            f"    [dim]{a.age}[/dim]",
            markup=True,
        )


class AgentsApp(App):
    """autobox agents TUI."""

    TITLE = "autobox"
    CSS = """
    Screen {
        background: $surface;
    }

    #header {
        height: 3;
        content-align: center middle;
        background: $primary-background;
        color: $text;
        text-style: bold;
        padding: 0 2;
    }

    #prompt-container {
        height: auto;
        padding: 1 2;
    }

    #prompt {
        margin: 0;
    }

    #agents-label {
        padding: 0 2;
        color: $text-muted;
        text-style: bold;
    }

    #agent-list {
        height: 1fr;
        margin: 0 2;
        border: round $primary;
    }

    #empty-state {
        height: 1fr;
        margin: 0 2;
        padding: 2 4;
        border: round $primary;
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
        background: $primary-background;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete", "Delete"),
        Binding("escape", "focus_prompt", "Prompt", show=False),
    ]

    project_dir: var[str] = var("")
    agents: var[list[Agent]] = var(list)

    def compose(self) -> ComposeResult:
        yield Static("", id="header")
        with Vertical(id="prompt-container"):
            yield Input(
                placeholder="Start new agent with a task...",
                id="prompt",
            )
        yield Label(" Agents", id="agents-label")
        yield ListView(id="agent-list")
        yield Static(
            "No agents yet. Type a task above to start one.",
            id="empty-state",
        )
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.project_dir = get_project_dir()
        except Exception:
            self.project_dir = os.getcwd()

        short_path = self.project_dir.replace(os.path.expanduser("~"), "~")
        self.query_one("#header", Static).update(
            f" autobox  [dim]─[/dim]  {short_path} "
        )
        self.refresh_agents()

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
        self.launch_autobox(name=name, prompt=text)

    @on(ListView.Selected, "#agent-list")
    def on_agent_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, AgentItem):
            self.launch_autobox(worktree=event.item.agent.path)

    def action_delete(self) -> None:
        agent_list = self.query_one("#agent-list", ListView)
        if agent_list.index is not None and agent_list.index < len(self.agents):
            agent = self.agents[agent_list.index]
            err = delete_agent(self.project_dir, agent)
            if err:
                self.notify(f"Delete failed: {err}", severity="error")
            else:
                self.notify(f"Deleted {agent.name}")
            self.refresh_agents()

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", Input).focus()

    @work(thread=True)
    def launch_autobox(
        self,
        name: str | None = None,
        prompt: str | None = None,
        worktree: str | None = None,
    ) -> None:
        cmd = [AUTOBOX_BIN]
        if name:
            cmd.extend(["--name", name])
        if worktree:
            cmd.extend(["--worktree", worktree])
        cmd.append("--")
        if prompt:
            cmd.append(prompt)

        with self.app.suspend():
            subprocess.run(cmd)

        self.app.call_from_thread(self.refresh_agents)


def main() -> None:
    app = AgentsApp()
    app.run()


if __name__ == "__main__":
    main()
