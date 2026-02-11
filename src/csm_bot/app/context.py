"""Custom context for telegram handlers with convenient runtime access."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, TYPE_CHECKING

from telegram.ext import ContextTypes

from csm_bot.app.storage import BotStorage, ChatStorage

if TYPE_CHECKING:
    from csm_bot.app.runtime import BotRuntime


class BotContext(ContextTypes.DEFAULT_TYPE):
    """Extend the default context with shortcuts for runtime and bot/chat storage."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._runtime: BotRuntime | None = None
        self._bot_storage: BotStorage | None = None
        self._chat_storage_cache: dict[int, ChatStorage] = {}

    @property
    def runtime(self) -> "BotRuntime":
        if self._runtime is None:
            from csm_bot.app.runtime import get_runtime_from_application

            self._runtime = get_runtime_from_application(self.application)
        return self._runtime

    @property
    def bot_storage(self) -> BotStorage:
        if self._bot_storage is None:
            raw_bot_data: MutableMapping[str, Any] = self.bot_data
            self._bot_storage = BotStorage(raw_bot_data)
        return self._bot_storage

    def chat_storage(
        self,
        chat_data: MutableMapping[str, Any] | None = None,
    ) -> ChatStorage:
        data = chat_data if chat_data is not None else self.chat_data
        if data is None:
            raise RuntimeError("Chat storage requested without chat data")
        key = id(data)
        cached = self._chat_storage_cache.get(key)
        if cached is not None:
            return cached
        storage = ChatStorage(data)
        self._chat_storage_cache[key] = storage
        return storage
