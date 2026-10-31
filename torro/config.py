import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRETS = ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    telegram_owner_id: int
    workspace: Path
    data_dir: Path
    chat_model: str
    task_model: str
    daily_budget_inr: float
    usd_to_inr: float
    approval_timeout_s: int
    shell_allowlist: tuple[str, ...]


def load_config(toml_path: Path = REPO_ROOT / "torro.toml", env: Mapping[str, str] | None = None) -> Config:
    if env is None:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
        env = os.environ
    missing = [k for k in SECRETS if not env.get(k)]
    if missing:
        raise ConfigError(f"Missing secrets in .env: {', '.join(missing)}")
    try:
        owner_id = int(env["TELEGRAM_OWNER_ID"])
    except ValueError:
        raise ConfigError("TELEGRAM_OWNER_ID must be a number") from None

    s = tomllib.loads(Path(toml_path).read_text(encoding="utf-8"))
    workspace = Path(s.get("workspace", "D:/Tech/Torro/workspace")).resolve()
    # TORRO must never be able to edit its own code or safety rules.
    if workspace == REPO_ROOT or REPO_ROOT in workspace.parents:
        raise ConfigError(f"workspace must be outside the TORRO source tree ({REPO_ROOT})")
    data_dir = Path(s.get("data_dir", REPO_ROOT / "data")).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
        telegram_owner_id=owner_id,
        workspace=workspace,
        data_dir=data_dir,
        chat_model=s.get("chat_model", "claude-sonnet-5-5"),
        task_model=s.get("task_model", "claude-opus-5-5"),
        daily_budget_inr=float(s.get("daily_budget_inr", 100)),
        usd_to_inr=float(s.get("usd_to_inr", 88.0)),
        approval_timeout_s=int(s.get("approval_timeout_s", 300)),
        shell_allowlist=tuple(s.get("shell_allowlist", (
            "ls", "dir", "cat", "type", "echo", "pwd", "mkdir", "git status", "git log", "git diff",
        ))),
    )
