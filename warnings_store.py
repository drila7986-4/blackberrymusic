from db import warnings_col

MAX_WARNINGS = 3


def _key(chat_id: int, user_id: int) -> str:
    return f"{chat_id}:{user_id}"


async def add_warning(chat_id: int, user_id: int, reason: str) -> int:
    """Ek warning add karta hai aur total warning count return karta hai."""
    k = _key(chat_id, user_id)
    await warnings_col.update_one(
        {"_id": k}, {"$push": {"reasons": reason}}, upsert=True
    )
    doc = await warnings_col.find_one({"_id": k})
    return len(doc.get("reasons", []))


async def get_warnings(chat_id: int, user_id: int) -> list:
    doc = await warnings_col.find_one({"_id": _key(chat_id, user_id)})
    return doc.get("reasons", []) if doc else []


async def reset_warnings(chat_id: int, user_id: int):
    await warnings_col.delete_one({"_id": _key(chat_id, user_id)})
