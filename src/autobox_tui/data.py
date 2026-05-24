"""Git worktree scanning and data models for autobox agents TUI."""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass


@dataclass
class Agent:
    name: str
    branch: str
    path: str
    added: int = 0
    modified: int = 0
    deleted: int = 0
    mtime: float = 0.0

    @property
    def status_summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"+{self.added}")
        if self.modified:
            parts.append(f"~{self.modified}")
        if self.deleted:
            parts.append(f"-{self.deleted}")
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


def get_project_dir() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


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

    agents = []
    current_path = ""
    current_branch = ""

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree ") :]
        elif line.startswith("branch refs/heads/"):
            current_branch = line[len("branch refs/heads/") :]
        elif line == "":
            if current_path.startswith(worktree_base):
                name = os.path.basename(current_path)
                agent = Agent(
                    name=name,
                    branch=current_branch,
                    path=current_path,
                    mtime=_get_mtime(current_path),
                )
                _fill_status(agent)
                agents.append(agent)
            current_path = ""
            current_branch = ""

    # Handle last entry if no trailing blank line
    if current_path.startswith(worktree_base):
        name = os.path.basename(current_path)
        agent = Agent(
            name=name,
            branch=current_branch,
            path=current_path,
            mtime=_get_mtime(current_path),
        )
        _fill_status(agent)
        agents.append(agent)

    agents.sort(key=lambda a: a.mtime, reverse=True)
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
        if x == "?" or y == "?":
            agent.added += 1
        elif x in ("M", "R", "C") or y in ("M", "R", "C"):
            agent.modified += 1
        elif x == "D" or y == "D":
            agent.deleted += 1
        elif x == "A":
            agent.added += 1


def delete_agent(project_dir: str, agent: Agent) -> str | None:
    """Delete a worktree and its branch. Returns error message or None."""
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
