import asyncio
import logging
import os
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Verdict = Literal["allow", "ask", "deny"]
Approver = Callable[[str], Awaitable[bool]]  # prompt text -> approved?

log = logging.getLogger("torro.activity")

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


def _safe_arg(arg: str, workspace: Path) -> bool:
    if arg.startswith("-"):
        if "=" not in arg:
            return True
        arg = arg.split("=", 1)[1]  # --output=<path>
    # "env:", "HKLM:" etc. are PowerShell drives, not files; only "X:/..." drive paths are allowed.
    if ":" in arg and not (len(arg) >= 2 and arg[1] == ":" and arg[0].isalpha() and ":" not in arg[2:]):
        return False
    return _inside(arg, workspace)


def _allowlisted(command: str, allowlist: Sequence[str], workspace: Path) -> bool:
    if any(c in SHELL_METACHARS for c in command):
        return False
    words = command.split()
    for entry in allowlist:
        n = len(entry.split())
        if words[:n] == entry.split():
            # Every argument must stay inside the workspace, or the command needs approval.
            return all(_safe_arg(a, workspace) for a in words[n:])
    return False


def _glob_prefix(pattern: str) -> str:
    return re.split(r"[*?\[{]", pattern, maxsplit=1)[0]


def classify(tool_name: str, tool_input: dict, workspace: Path, shell_allowlist: Sequence[str]) -> Decision:
    if tool_name.startswith("mcp__torro__") or tool_name in FREE_TOOLS:
        return Decision("allow", "free tool")
    if tool_name in FILE_TOOLS:
        paths = [tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or "."]
        # Glob's pattern and Grep's glob can carry a path of their own.
        pattern = tool_input.get("pattern") if tool_name == "Glob" else tool_input.get("glob")
        if pattern and _glob_prefix(pattern):
            paths.append(_glob_prefix(pattern))
        for path in paths:
            if not _inside(path, workspace):
                return Decision("deny", f"{path} is outside TORRO's workspace")
        return Decision("allow", "inside workspace")
    if tool_name in SHELL_TOOLS:
        if _allowlisted(tool_input.get("command", ""), shell_allowlist, workspace):
            return Decision("allow", "allowlisted command")
        return Decision("ask", "shell command needs approval")
    return Decision("ask", "unknown tool needs approval")


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason,
    }}


def _describe(tool_name: str, tool_input: dict) -> str:
    detail = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("url") or str(tool_input)
    return f"TORRO wants to use {tool_name}:\n{str(detail)[:300]}"


def make_pre_tool_hook(workspace: Path, shell_allowlist: Sequence[str], approver: Approver, timeout_s: float):
    """PreToolUse hook: the single gate every tool call passes through."""

    async def hook(input_data, tool_use_id, context) -> dict:
        name, inp = input_data.get("tool_name", "?"), input_data.get("tool_input", {})
        try:
            d = classify(name, inp, workspace, shell_allowlist)
            if d.verdict == "ask":
                try:
                    ok = await asyncio.wait_for(approver(_describe(name, inp)), timeout_s)
                    d = Decision("allow", "Yogesh approved") if ok else Decision("deny", "Yogesh declined")
                except asyncio.TimeoutError:
                    d = Decision("deny", "No answer from Yogesh")
        except Exception:
            # A safety gate fails closed.
            log.exception("policy hook error")
            d = Decision("deny", "Safety check failed; action blocked")
        log.info("%s %s %s | %s", d.verdict.upper(), name, str(inp)[:200], d.reason)
        if d.verdict == "deny":
            return _deny(d.reason)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}

    return hook
