"""Git worktree scanning and data models for autobox agents TUI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class Agent:
    name: str
    branch: str
    path: str
    added: int = 0
    modified: int = 0
    deleted: int = 0
    unmerged: int = 0
    mtime: float = 0.0
    running: bool = False
    container_name: str = ""

    @property
    def status_summary(self) -> str:
        if self.running:
            return "running"
        parts = []
        if self.added:
            parts.append(f"+{self.added}")
        if self.modified:
            parts.append(f"~{self.modified}")
        if self.deleted:
            parts.append(f"-{self.deleted}")
        if self.unmerged:
            parts.append(f"!{self.unmerged}")
        return " ".join(parts) if parts else "clean"

    @property
    def age(self) -> str:
        delta = time.time() - self.mtime
        if delta < 60:
            return "just now"
        if delta < 3600:
            m = int(delta / 60)
            return f"{m} min ago"
        if delta < 86400:
            h = int(delta / 3600)
            return f"{h}h ago"
        d = int(delta / 86400)
        return f"{d}d ago"


AUTOBOX_BIN = shutil.which("autobox") or "autobox"


def get_project_dir() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _get_running_containers() -> set[str]:
    """Get names of all running autobox containers."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=autobox-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return set(result.stdout.strip().splitlines()) if result.stdout.strip() else set()


def _get_exited_containers() -> set[str]:
    """Get names of exited (stopped) autobox containers."""
    result = subprocess.run(
        [
            "docker", "ps", "-a",
            "--filter", "name=autobox-",
            "--filter", "status=exited",
            "--format", "{{.Names}}",
        ],
        capture_output=True,
        text=True,
    )
    return set(result.stdout.strip().splitlines()) if result.stdout.strip() else set()


def list_agents(project_dir: str | None = None) -> list[Agent]:
    if project_dir is None:
        project_dir = get_project_dir()

    worktree_base = os.path.join(project_dir, ".claude", "worktrees")
    if not os.path.isdir(worktree_base):
        return []

    result = subprocess.run(
        ["git", "-C", project_dir, "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )

    running = _get_running_containers()

    agents = []
    current_path = ""
    current_branch = ""

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/"):
            current_branch = line[len("branch refs/heads/"):]
        elif line == "":
            if current_path.startswith(worktree_base):
                name = os.path.basename(current_path)
                container_name = f"autobox-{name}"
                is_running = container_name in running
                agent = Agent(
                    name=name,
                    branch=current_branch,
                    path=current_path,
                    mtime=_get_mtime(current_path),
                    running=is_running,
                    container_name=container_name,
                )
                if not is_running:
                    _fill_status(agent)
                agents.append(agent)
            current_path = ""
            current_branch = ""

    # Handle last entry if no trailing blank line
    if current_path.startswith(worktree_base):
        name = os.path.basename(current_path)
        container_name = f"autobox-{name}"
        is_running = container_name in running
        agent = Agent(
            name=name,
            branch=current_branch,
            path=current_path,
            mtime=_get_mtime(current_path),
            running=is_running,
            container_name=container_name,
        )
        if not is_running:
            _fill_status(agent)
        agents.append(agent)

    agents.sort(key=lambda a: (not a.running, -a.mtime))
    return agents


def _get_mtime(path: str) -> float:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def _fill_status(agent: Agent) -> None:
    result = subprocess.run(
        ["git", "-C", agent.path, "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if not line or len(line) < 2:
            continue
        x, y = line[0], line[1]
        if x == "U" or y == "U":
            agent.unmerged += 1
        elif x == "?" or y == "?":
            agent.added += 1
        elif x in ("M", "R", "C") or y in ("M", "R", "C"):
            agent.modified += 1
        elif x == "D" or y == "D":
            agent.deleted += 1
        elif x == "A":
            agent.added += 1


def cleanup_agent(project_dir: str, agent: Agent) -> None:
    """Run autobox cleanup for a stopped agent."""
    subprocess.run(
        [AUTOBOX_BIN, "cleanup", agent.name, project_dir],
        capture_output=True,
        text=True,
    )


def stop_agent(agent: Agent) -> None:
    """Stop a running agent's container."""
    subprocess.run(
        ["docker", "stop", agent.container_name],
        capture_output=True,
        text=True,
    )


def delete_agent(project_dir: str, agent: Agent) -> str | None:
    """Stop, clean up, and force-remove an agent. Returns error message or None."""
    if agent.running:
        stop_agent(agent)

    cleanup_agent(project_dir, agent)

    # Force-remove worktree if it still exists (cleanup keeps dirty worktrees)
    if os.path.isdir(agent.path):
        result = subprocess.run(
            ["git", "-C", project_dir, "worktree", "remove", agent.path, "--force"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return result.stderr.strip()

    subprocess.run(
        ["git", "-C", project_dir, "branch", "-D", agent.branch],
        capture_output=True,
        text=True,
    )
    return None


def slugify(text: str, max_length: int = 50) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "agent"
