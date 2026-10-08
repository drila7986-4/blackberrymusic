from db import coins_col, game_users_col
from pymongo import ReturnDocument


async def get_coins(user_id: int) -> int:
    doc = await coins_col.find_one({"_id": int(user_id)})
    return int(doc.get("coins", 0)) if doc else 0


async def add_coins(user_id: int, amount: int) -> int:
    result = await coins_col.find_one_and_update(
        {"_id": int(user_id)},
        {"$inc": {"coins": int(amount)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(result.get("coins", 0)) if result else await get_coins(user_id)


async def top_coins(limit: int = 10):
    cursor = coins_col.find({"coins": {"$gt": 0}}).sort("coins", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def mark_game_user_started(user_id: int) -> None:
    await game_users_col.update_one({"_id": int(user_id)}, {"$set": {"started": True}}, upsert=True)

async def has_started_in_dm(user_id: int) -> bool:
    doc = await game_users_col.find_one({"_id": int(user_id), "started": True})
    return bool(doc)
