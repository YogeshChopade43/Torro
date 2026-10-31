import asyncio
import contextlib
import logging
import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from torro.config import Config

log = logging.getLogger("torro.telegram")
LIMIT = 4096  # Telegram's max message length


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            parts.append(text[:limit])
            text = text[limit:]
        else:
            parts.append(text[:cut])
            text = text[cut + 1:]
    if text:
        parts.append(text)
    return parts


def is_owner(user_id: int | None, owner_id: int) -> bool:
    return user_id is not None and user_id == owner_id


class TelegramFront:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.brain = None
        self._pending: dict[str, asyncio.Future] = {}
        # concurrent_updates: an approval button press must be handled while chat() is waiting on it.
        self.app = (Application.builder().token(cfg.telegram_bot_token).concurrent_updates(True)
                    .post_init(self._post_init).post_shutdown(self._post_shutdown).build())
        self.app.add_handler(CommandHandler("start", self._on_start))
        self.app.add_handler(CommandHandler("stop", self._on_stop))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        self.app.add_handler(CallbackQueryHandler(self._on_button))

    def attach(self, brain) -> None:
        self.brain = brain

    def _owner(self, update: Update) -> bool:
        user = update.effective_user
        return is_owner(user.id if user else None, self.cfg.telegram_owner_id)

    async def approve(self, prompt: str) -> bool:
        key = secrets.token_hex(4)
        fut = asyncio.get_running_loop().create_future()
        self._pending[key] = fut
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"ok:{key}"),
                                         InlineKeyboardButton("❌ Deny", callback_data=f"no:{key}")]])
        try:
            await self.app.bot.send_message(self.cfg.telegram_owner_id, prompt, reply_markup=buttons)
            return await fut
        finally:
            self._pending.pop(key, None)  # also on timeout, so a late press reads "expired"

    async def notify(self, text: str) -> None:
        for part in split_message(text):
            await self.app.bot.send_message(self.cfg.telegram_owner_id, part)

    async def _on_button(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._owner(update):
            return
        q = update.callback_query
        action, _, key = (q.data or "").partition(":")
        fut = self._pending.get(key)
        if fut is None or fut.done():
            await q.answer("This request has expired.")
            return
        approved = action == "ok"
        fut.set_result(approved)
        await q.answer()
        await q.edit_message_text(f"{q.message.text}\n\n{'✅ Approved' if approved else '❌ Denied'}")

    async def _on_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self._owner(update):
            await update.message.reply_text("Good to see you, Yogesh. TORRO is online.")

    async def _on_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self._owner(update):
            n = await self.brain.stop_everything()
            await update.message.reply_text(f"Stopped {n} task(s), Yogesh.")

    async def _on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._owner(update):
            return
        text = update.message.text
        if text.strip().lower() == "stop everything":
            await self._on_stop(update, ctx)
            return
        typing = asyncio.create_task(self._keep_typing(update.effective_chat.id))
        try:
            reply = await self.brain.chat(text)
        except Exception:
            log.exception("chat failed")
            reply = "Something went wrong, Yogesh — I've logged it."
        finally:
            typing.cancel()
        for part in split_message(reply) or ["…"]:
            await update.message.reply_text(part)

    async def _keep_typing(self, chat_id: int) -> None:
        with contextlib.suppress(Exception):
            while True:
                await self.app.bot.send_chat_action(chat_id, ChatAction.TYPING)
                await asyncio.sleep(4)

    async def _post_init(self, app: Application) -> None:
        await self.brain.start()

    async def _post_shutdown(self, app: Application) -> None:
        await self.brain.close()

    def run(self) -> None:
        self.app.run_polling()
