import asyncio
from pathlib import Path

import pytest

from torro.policy import classify, make_pre_tool_hook

WS = Path("D:/ws")
AL = ["ls", "git status"]


@pytest.mark.parametrize("path", ["notes.md", "D:/ws/a/b.txt", "d:/WS/x.txt"])
def test_file_inside_allowed(path):
    assert classify("Write", {"file_path": path}, WS, AL).verdict == "allow"


@pytest.mark.parametrize("path", ["../secret.txt", "D:/ws/../other/x", "C:/Windows/x", "D:/wsevil/x"])
def test_file_outside_denied(path):
    assert classify("Read", {"file_path": path}, WS, AL).verdict == "deny"


def test_file_tool_without_path_is_workspace():
    assert classify("Glob", {"pattern": "*.md"}, WS, AL).verdict == "allow"


@pytest.mark.parametrize("cmd,verdict", [
    ("ls", "allow"), ("git status -s", "allow"),
    ("git statusx", "ask"), ("ls; rm -rf /", "ask"), ("ls && del x", "ask"),
    ("echo $(whoami)", "ask"), ("python x.py", "ask"),
])
def test_shell(cmd, verdict):
    assert classify("Bash", {"command": cmd}, WS, AL).verdict == verdict


def test_torro_and_web_tools_allowed():
    assert classify("mcp__torro__start_background_task", {}, WS, AL).verdict == "allow"
    assert classify("WebFetch", {"url": "https://x.com"}, WS, AL).verdict == "allow"


def test_unknown_tool_asks():
    assert classify("SomeNewTool", {}, WS, AL).verdict == "ask"


def run(hook, name, inp):
    return asyncio.run(hook({"tool_name": name, "tool_input": inp, "hook_event_name": "PreToolUse"}, "id1", {}))


def denied(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def test_ask_approved():
    async def yes(_): return True
    assert not denied(run(make_pre_tool_hook(WS, AL, yes, 1), "Bash", {"command": "python x.py"}))


def test_ask_declined():
    async def no(_): return False
    assert denied(run(make_pre_tool_hook(WS, AL, no, 1), "Bash", {"command": "python x.py"}))


def test_ask_timeout_denies():
    async def never(_):
        await asyncio.sleep(10)
        return True
    out = run(make_pre_tool_hook(WS, AL, never, 0.05), "Bash", {"command": "python x.py"})
    assert denied(out) and "No answer" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_deny_never_asks():
    asked = []
    async def spy(p):
        asked.append(p)
        return True
    assert denied(run(make_pre_tool_hook(WS, AL, spy, 1), "Read", {"file_path": "C:/Windows/x"}))
    assert asked == []


# --- final-review fixes ---

UNSAFE_AL = ["cat", "type", "ls", "dir", "mkdir", "git log", "git diff", "pwd", "echo"]


@pytest.mark.parametrize("cmd", [
    "cat D:/Tech/Torro/Torro/.env", "cat ../Torro/.env", "type C:/Users/yoges/.ssh/id_ed25519",
    "ls C:/Users/yoges", "dir env:", "mkdir C:/evil", "git log --output=D:/x/policy.py",
    "git diff --no-index D:/x/.env /dev/null",
])
def test_allowlisted_command_with_outside_argument_asks(cmd):
    assert classify("Bash", {"command": cmd}, WS, UNSAFE_AL).verdict == "ask"


def test_allowlisted_command_inside_workspace_still_free():
    assert classify("Bash", {"command": "cat notes.md"}, WS, UNSAFE_AL).verdict == "allow"


def test_default_allowlist_has_no_code_running_commands():
    from torro.config import DEFAULT_SHELL_ALLOWLIST
    assert not any(e.split()[0] in ("git", "python", "cat", "type", "ls", "dir") for e in DEFAULT_SHELL_ALLOWLIST)


@pytest.mark.parametrize("tool,inp", [
    ("Glob", {"pattern": "C:/Users/**/*"}), ("Glob", {"pattern": "../Torro/**"}),
    ("Grep", {"pattern": "KEY", "glob": "D:/Tech/Torro/Torro/*.env"}),
])
def test_glob_patterns_outside_denied(tool, inp):
    assert classify(tool, inp, WS, AL).verdict == "deny"


def test_glob_relative_pattern_allowed():
    assert classify("Glob", {"pattern": "**/*.md"}, WS, AL).verdict == "allow"


def test_hook_error_denies():
    async def boom(_):
        raise ConnectionError("telegram down")
    assert denied(run(make_pre_tool_hook(WS, AL, boom, 1), "Bash", {"command": "python x.py"}))
    assert denied(run(make_pre_tool_hook(WS, AL, boom, 1), "Read", {"file_path": ["a"]}))
