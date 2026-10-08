from db import sudo_col


async def get_sudo_users() -> set:
    cursor = sudo_col.find({}, {"_id": 1})
    return {doc["_id"] async for doc in cursor}


async def add_sudo(user_id: int):
    await sudo_col.update_one(
        {"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True
    )


async def remove_sudo(user_id: int):
    await sudo_col.delete_one({"_id": user_id})
