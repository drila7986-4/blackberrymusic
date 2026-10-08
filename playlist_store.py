from typing import Optional

from db import playlist_col

MAX_PLAYLIST_SIZE = 50


async def add_to_playlist(chat_id: int, title: str, url: Optional[str]) -> bool:
    """Ek chat ki playlist me gaana add karta hai. Playlist full ho to False deta hai."""
    doc = await playlist_col.find_one({"_id": chat_id})
    items = doc.get("items", []) if doc else []
    if len(items) >= MAX_PLAYLIST_SIZE:
        return False
    await playlist_col.update_one(
        {"_id": chat_id},
        {"$push": {"items": {"title": title, "url": url}}},
        upsert=True,
    )
    return True


async def get_playlist(chat_id: int) -> list:
    doc = await playlist_col.find_one({"_id": chat_id})
    return doc.get("items", []) if doc else []


async def remove_from_playlist(chat_id: int, index: int) -> bool:
    """1-indexed removal, matching what /playlist shows the user."""
    items = await get_playlist(chat_id)
    if index < 1 or index > len(items):
        return False
    items.pop(index - 1)
    await playlist_col.update_one({"_id": chat_id}, {"$set": {"items": items}}, upsert=True)
    return True


async def clear_playlist(chat_id: int):
    await playlist_col.update_one({"_id": chat_id}, {"$set": {"items": []}}, upsert=True)
