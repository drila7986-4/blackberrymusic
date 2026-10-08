from db import gban_col


async def get_gban_list() -> dict:
    """Returns {user_id: reason}."""
    cursor = gban_col.find({})
    return {doc["_id"]: doc.get("reason", "Koi reason nahi diya gaya") async for doc in cursor}


async def is_gbanned(user_id: int) -> bool:
    doc = await gban_col.find_one({"_id": user_id})
    return doc is not None


async def add_gban(user_id: int, reason: str = "Koi reason nahi diya gaya"):
    await gban_col.update_one(
        {"_id": user_id}, {"$set": {"reason": reason}}, upsert=True
    )


async def remove_gban(user_id: int):
    await gban_col.delete_one({"_id": user_id})
