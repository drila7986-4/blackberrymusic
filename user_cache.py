"""
Sirf un users ka data cache karta hai jinhone bot se **directly interact** kiya hai —
koi command chalaya, ya kisi moderation action (warn/ban/mute/kick/sudo) ka target bane.
Ye kisi group ke saare members ko passively track NAHI karta — sirf wahi log jo bot se
kisi na kisi tarah touch huye hain.
"""

from datetime import datetime, timezone
from typing import Optional

from db import db

user_cache_col = db["known_users"]


async def cache_user(user, reason: str = "command"):
    """Ek user ka basic info (naam/username) upsert karta hai.
    `reason` batata hai kis wajah se cache hua (command chalaya / moderation target hua)."""
    if not user:
        return
    await user_cache_col.update_one(
        {"_id": user.id},
        {
            "$set": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "last_reason": reason,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def get_cached_user(user_id: int) -> Optional[dict]:
    return await user_cache_col.find_one({"_id": user_id})
