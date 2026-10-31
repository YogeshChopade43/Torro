import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Verdict = Literal["allow", "ask", "deny"]

FREE_TOOLS = {"WebSearch", "WebFetch", "TodoWrite"}
FILE_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
SHELL_TOOLS = {"Bash", "PowerShell"}
SHELL_METACHARS = set(";&|><$`()\n")


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str


def _inside(path: str, workspace: Path) -> bool:
    ws = os.path.normcase(os.path.abspath(workspace))
    p = os.path.normcase(os.path.abspath(os.path.join(ws, path)))
    try:
        return os.path.commonpath([ws, p]) == ws
    except ValueError:  # different drives
        return False


def _allowlisted(command: str, allowlist: Sequence[str]) -> bool:
    if any(c in SHELL_METACHARS for c in command):
        return False
    words = command.split()
    return any(words[: len(e.split())] == e.split() for e in allowlist)


def classify(tool_name: str, tool_input: dict, workspace: Path, shell_allowlist: Sequence[str]) -> Decision:
    if tool_name.startswith("mcp__torro__") or tool_name in FREE_TOOLS:
        return Decision("allow", "free tool")
    if tool_name in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or "."
        if _inside(path, workspace):
            return Decision("allow", "inside workspace")
        return Decision("deny", f"{path} is outside TORRO's workspace")
    if tool_name in SHELL_TOOLS:
        if _allowlisted(tool_input.get("command", ""), shell_allowlist):
            return Decision("allow", "allowlisted command")
        return Decision("ask", "shell command needs approval")
    return Decision("ask", "unknown tool needs approval")
