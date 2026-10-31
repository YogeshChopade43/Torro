from pathlib import Path

import pytest

from torro.config import ConfigError, load_config

REPO_ROOT = Path(__file__).parents[1]
FULL_ENV = {"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_OWNER_ID": "1"}


def write_toml(tmp_path, workspace=None):
    ws = workspace or str(tmp_path / "ws")
    p = tmp_path / "torro.toml"
    p.write_text(f'workspace = "{Path(ws).as_posix()}"\ndata_dir = "{(tmp_path / "data").as_posix()}"\n')
    return p


def test_missing_secret_names_it(tmp_path):
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_config(write_toml(tmp_path), env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_OWNER_ID": "1"})


def test_workspace_inside_repo_rejected(tmp_path):
    with pytest.raises(ConfigError, match="outside"):
        load_config(write_toml(tmp_path, workspace=str(REPO_ROOT / "ws")), env=FULL_ENV)


def test_loads_and_creates_workspace(tmp_path):
    cfg = load_config(write_toml(tmp_path, workspace=str(tmp_path / "ws")), env=FULL_ENV)
    assert cfg.workspace.is_dir() and cfg.telegram_owner_id == 1 and cfg.daily_budget_inr == 100
