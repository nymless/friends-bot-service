from asyncio import Lock
from weakref import WeakValueDictionary

_chat_locks: WeakValueDictionary[tuple[int, int], Lock] = WeakValueDictionary()


def get_bot_chat_lock(key: tuple[int, int]) -> Lock:
    """
    Returns an in-memory lock for a specific bot and chat.

    Locks are stored in a weak-reference dictionary and serialize draw handler
    execution for a bot/chat pair within a single application process.
    """
    lock = _chat_locks.get(key)

    if lock is None:
        lock = Lock()
        _chat_locks[key] = lock

    return lock
