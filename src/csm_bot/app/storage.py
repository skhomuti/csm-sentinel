"""Storage helpers wrapping the persistence-backed bot and chat state."""

import logging
from collections.abc import Iterable, MutableMapping
from pathlib import Path
from typing import Any, Dict, Set

from telegram.ext import BasePersistence, PicklePersistence

logger = logging.getLogger(__name__)


def create_persistence(storage_path: Path) -> BasePersistence:
    """Return the persistence backend used by the bot."""

    return PicklePersistence(filepath=storage_path / "persistence.pkl")


def ensure_int_set(values: Any) -> Set[int]:
    if values is None:
        return set()

    if isinstance(values, (set, frozenset)):
        items = values
        if all(isinstance(item, int) for item in items):
            return set(items) if isinstance(values, frozenset) else items
    else:
        try:
            items = set(values)
        except TypeError:  # pragma: no cover - defensive; unexpected types
            logger.warning("Ignoring malformed chat id container: %r", values)
            return set()

    result: Set[int] = set()
    for item in items:
        try:
            result.add(int(item))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Skipping non-integer chat id: %r", item)
    return result


def normalise_node_operator_map(mapping: Any) -> Dict[str, Set[int]]:
    if mapping is None:
        return {}

    try:
        items = mapping.items()
    except AttributeError:  # pragma: no cover - defensive
        logger.warning("Ignoring malformed node operator mapping: %r", mapping)
        return {}

    normalised: Dict[str, Set[int]] = {}
    for key, value in items:
        str_key = str(key)
        chats = ensure_int_set(value)
        if chats:
            normalised[str_key] = chats
        else:
            # retain empty sets to preserve explicit registrations
            normalised[str_key] = set()
    return normalised


def normalise_node_operator_ids(values: Any) -> Set[str]:
    if not values:
        return set()
    try:
        return {str(value) for value in values if value is not None}
    except TypeError:  # pragma: no cover - defensive
        logger.warning("Ignoring malformed node operator list: %r", values)
        return set()


class BlockState:
    """Helper exposing the persisted latest processed block."""

    def __init__(self, bot_data: MutableMapping[str, Any]):
        self._bot_data = bot_data
        self._bot_data["block"] = int(self._bot_data.get("block", 0) or 0)

    @property
    def value(self) -> int:
        return self._bot_data["block"]

    def update(self, block: int) -> None:
        self._bot_data["block"] = int(block)

    def __int__(self) -> int:  # pragma: no cover - convenience
        return int(self.value)


class ChatIdSet:
    """Helper providing set-like operations over stored chat identifiers."""

    def __init__(self, bot_data: MutableMapping[str, Any], key: str):
        self._bot_data = bot_data
        self._key = key
        self._bot_data[self._key] = ensure_int_set(self._bot_data.get(self._key))

    def add(self, chat_id: int) -> None:
        self._values.add(int(chat_id))

    def remove(self, chat_id: int) -> None:
        self._values.discard(int(chat_id))

    def contains(self, chat_id: int) -> bool:
        return int(chat_id) in self._values

    def all(self) -> Set[int]:
        return set(self._values)

    def migrate_chat_id(self, old_chat_id: int, new_chat_id: int) -> bool:
        """Replace an existing chat id with a new one.

        Returns True when the set was updated.
        """

        old_id = int(old_chat_id)
        new_id = int(new_chat_id)
        if old_id == new_id:
            return False
        if old_id not in self._values:
            return False
        self._values.discard(old_id)
        self._values.add(new_id)
        return True

    @property
    def _values(self) -> Set[int]:
        return self._bot_data[self._key]


class NodeOperatorChats:
    """Helper for mapping node operator identifiers to subscribed chats."""

    def __init__(self, bot_data: MutableMapping[str, Any], key: str = "no_ids_to_chats"):
        self._bot_data = bot_data
        self._key = key
        self._bot_data[self._key] = normalise_node_operator_map(self._bot_data.get(self._key))

    def subscribe(self, node_operator_id: str, chat_id: int) -> None:
        key = self._normalise_node_operator_id(node_operator_id)
        chats = self._mapping.setdefault(key, set())
        chats.add(int(chat_id))

    def unsubscribe(self, node_operator_id: str, chat_id: int) -> None:
        key = self._normalise_node_operator_id(node_operator_id)
        chats = self._mapping.get(key)
        if chats is None:
            return
        chats.discard(int(chat_id))
        if not chats:
            # keep empty sets to avoid accidental re-creation churn
            self._mapping[key] = set()

    def chats_for(self, node_operator_id: str) -> Set[int]:
        key = self._normalise_node_operator_id(node_operator_id)
        return set(self._mapping.get(key, set()))

    def ids(self) -> Set[str]:
        return set(self._mapping.keys())

    def resolve_targets(
        self,
        node_operator_ids: Iterable[str],
        actual_chat_ids: Iterable[int],
    ) -> Set[int]:
        desired = {self._normalise_node_operator_id(no_id) for no_id in node_operator_ids}
        actual = set(actual_chat_ids)
        targets: Set[int] = set()
        for no_id in desired:
            targets.update(self._mapping.get(no_id, set()))
        return targets.intersection(actual)

    def subscription_counts(
        self,
        actual_chat_ids: Iterable[int],
        user_ids: Iterable[int],
        group_ids: Iterable[int],
        channel_ids: Iterable[int],
    ) -> Dict[str, Dict[str, int]]:
        actual = set(actual_chat_ids)
        users = set(user_ids)
        groups = set(group_ids)
        channels = set(channel_ids)

        results: Dict[str, Dict[str, int]] = {}
        for no_id, chats in self._mapping.items():
            active = chats.intersection(actual)
            if not active:
                continue
            results[no_id] = {
                "total": len(active),
                "users": len(active.intersection(users)),
                "groups": len(active.intersection(groups)),
                "channels": len(active.intersection(channels)),
            }
        return results

    def migrate_chat_id(self, old_chat_id: int, new_chat_id: int) -> int:
        """Replace an existing chat id with a new one across all node operators.

        Returns the number of node operators whose chat set was updated.
        """

        old_id = int(old_chat_id)
        new_id = int(new_chat_id)
        if old_id == new_id:
            return 0

        updated = 0
        for chats in self._mapping.values():
            if old_id in chats:
                chats.discard(old_id)
                chats.add(new_id)
                updated += 1
        return updated

    @property
    def _mapping(self) -> Dict[str, Set[int]]:
        return self._bot_data[self._key]

    @staticmethod
    def _normalise_node_operator_id(node_operator_id: str) -> str:
        return str(node_operator_id)


class BotStorage:
    """Utility wrapper around the application-wide bot data."""

    def __init__(self, bot_data: MutableMapping[str, Any]):
        self._bot_data = bot_data
        self._block = BlockState(bot_data)
        self._users = ChatIdSet(bot_data, "user_ids")
        self._groups = ChatIdSet(bot_data, "group_ids")
        self._channels = ChatIdSet(bot_data, "channel_ids")
        self._node_operator_chats = NodeOperatorChats(bot_data)

    @property
    def block(self) -> BlockState:
        return self._block

    @property
    def users(self) -> ChatIdSet:
        return self._users

    @property
    def groups(self) -> ChatIdSet:
        return self._groups

    @property
    def channels(self) -> ChatIdSet:
        return self._channels

    @property
    def node_operator_chats(self) -> NodeOperatorChats:
        return self._node_operator_chats

    def actual_chat_ids(self) -> Set[int]:
        return self.users.all().union(self.groups.all(), self.channels.all())

    def resolve_target_chats(self, node_operator_ids: Iterable[str]) -> Set[int]:
        return self.node_operator_chats.resolve_targets(node_operator_ids, self.actual_chat_ids())

    def subscription_counts(self) -> Dict[str, Dict[str, int]]:
        return self.node_operator_chats.subscription_counts(
            self.actual_chat_ids(),
            self.users.all(),
            self.groups.all(),
            self.channels.all(),
        )

    def migrate_chat_id(self, old_chat_id: int, new_chat_id: int) -> None:
        """Update stored indexes for a migrated chat id."""

        self.users.migrate_chat_id(old_chat_id, new_chat_id)
        self.groups.migrate_chat_id(old_chat_id, new_chat_id)
        self.channels.migrate_chat_id(old_chat_id, new_chat_id)
        self.node_operator_chats.migrate_chat_id(old_chat_id, new_chat_id)


class NodeOperatorSubscriptions:
    """Helper around per-chat node operator subscriptions."""

    def __init__(self, chat_data: MutableMapping[str, Any], key: str = "node_operators"):
        self._chat_data = chat_data
        self._key = key
        self._chat_data[self._key] = normalise_node_operator_ids(chat_data.get(self._key))

    def ids(self) -> Set[str]:
        return set(self._values)

    def follow(self, node_operator_id: str) -> None:
        self._values.add(str(node_operator_id))

    def unfollow(self, node_operator_id: str) -> bool:
        key = str(node_operator_id)
        if key in self._values:
            self._values.remove(key)
            return True
        return False

    @property
    def _values(self) -> Set[str]:
        return self._chat_data[self._key]


class ChatStorage:
    """Utility wrapper around per-chat data."""

    def __init__(self, chat_data: MutableMapping[str, Any]):
        self._chat_data = chat_data
        self._node_operators = NodeOperatorSubscriptions(chat_data)

    @property
    def node_operators(self) -> NodeOperatorSubscriptions:
        return self._node_operators
