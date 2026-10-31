# TORRO

Yogesh's personal AI assistant. Design: [docs/superpowers/specs/2026-11-01-torro-design.md](docs/superpowers/specs/2026-11-01-torro-design.md) · Roadmap: [docs/superpowers/plans/2026-11-01-torro-roadmap.md](docs/superpowers/plans/2026-11-01-torro-roadmap.md)

## Setup (Phase 1)

1. **Python 3.11+**: `py -3.11 -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`
2. **Telegram bot**: in Telegram, message **@BotFather** → `/newbot` → copy the token.
3. **Your Telegram user id**: message **@userinfobot** → copy the number.
4. **Anthropic API key**: console.anthropic.com → API keys. Also set a monthly spend limit there.
5. Copy `.env.example` to `.env` and fill in all three values.
6. Check `torro.toml`, especially `workspace` (TORRO's sandbox; must be outside this repo).

The Claude CLI ships inside `claude-agent-sdk`, so there's nothing else to install.

## Run

```
.venv\Scripts\python -m torro            # Telegram
.venv\Scripts\python -m torro --console  # terminal chat, for testing
.venv\Scripts\python -m pytest           # tests (free, no API calls)
```

On Telegram: `/stop` or "stop everything" cancels all running work.

Logs: `data/torro.log` (app) and `data/activity.log` (every tool TORRO used or was refused).
