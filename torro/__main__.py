import argparse
import asyncio
import logging

from torro.brain import Brain
from torro.config import load_config
from torro.ledger import CostLedger


def setup_logging(cfg) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(cfg.data_dir / "torro.log", encoding="utf-8")])
    activity = logging.FileHandler(cfg.data_dir / "activity.log", encoding="utf-8")
    activity.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logging.getLogger("torro.activity").addHandler(activity)


async def console(cfg) -> None:
    async def approve(prompt: str) -> bool:
        answer = await asyncio.to_thread(input, f"\n{prompt}\nAllow? [y/N] ")
        return answer.strip().lower() in ("y", "yes")

    async def notify(text: str) -> None:
        print(f"\n[TORRO] {text}\n")

    brain = Brain(cfg, CostLedger(cfg.data_dir / "costs.db", cfg.daily_budget_inr, cfg.usd_to_inr), approve, notify)
    await brain.start()
    print("TORRO console. Type 'exit' to quit, 'stop everything' to cancel tasks.")
    try:
        while True:
            text = (await asyncio.to_thread(input, "you> ")).strip()
            if text.lower() in ("exit", "quit"):
                break
            if text.lower() == "stop everything":
                print(f"Stopped {await brain.stop_everything()} task(s).")
            elif text:
                print(f"torro> {await brain.chat(text)}")
    finally:
        await brain.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="torro")
    parser.add_argument("--console", action="store_true", help="chat in the terminal instead of Telegram")
    args = parser.parse_args()
    cfg = load_config()
    setup_logging(cfg)
    if args.console:
        asyncio.run(console(cfg))
        return
    from torro.telegram_bot import TelegramFront

    front = TelegramFront(cfg)
    ledger = CostLedger(cfg.data_dir / "costs.db", cfg.daily_budget_inr, cfg.usd_to_inr)
    front.attach(Brain(cfg, ledger, front.approve, front.notify))
    front.run()


if __name__ == "__main__":
    main()
