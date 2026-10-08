from db import settings_col

DEFAULT_SETTINGS = {
    "welcome": True,
    "clean_service": False,
}


async def get_settings(chat_id: int) -> dict:
    """Ek chat ke saare settings laata hai, defaults ke saath merge karke."""
    doc = await settings_col.find_one({"_id": chat_id}) or {}
    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in doc.items() if k != "_id"})
    return merged


async def set_setting(chat_id: int, key: str, value):
    await settings_col.update_one(
        {"_id": chat_id}, {"$set": {key: value}}, upsert=True
    )
