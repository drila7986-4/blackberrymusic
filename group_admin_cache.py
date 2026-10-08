"""
Har group ke sirf **admins** ki list cache karta hai (poore members ki nahi) —
har 10 minute me refresh hoti hai. Ye ek chota, bounded snapshot hai jo /admins
jaisa hi public info store karta hai (koi bhi group member ye dekh sakta hai ki
kaun admin hai), sirf isse baar baar Telegram API call karne se bachne ke liye.
"""

from datetime import datetime, timezone
import asyncio

from pyrogram.enums import ChatMemberStatus, ChatMembersFilter, ChatType

from db import db

admin_cache_col = db["group_admin_cache"]

REFRESH_INTERVAL_SECONDS = 10 * 60  # 10 minutes


async def refresh_all_admin_caches(bot):
    """Bot jitne bhi groups me hai, un sabke admins ki list refresh karta hai."""
    async for dialog in bot.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            continue
        admins = []
        try:
            async for member in bot.get_chat_members(chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
                admins.append(
                    {
                        "id": member.user.id,
                        "name": member.user.first_name,
                        "username": member.user.username,
                        "status": "owner" if member.status == ChatMemberStatus.OWNER else "admin",
                    }
                )
        except Exception:
            continue

        await admin_cache_col.update_one(
            {"_id": chat.id},
            {
                "$set": {
                    "title": chat.title,
                    "admins": admins,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )


async def admin_cache_loop(bot):
    """Har REFRESH_INTERVAL_SECONDS (10 min) me admin cache refresh karta hai, hamesha ke liye."""
    while True:
        try:
            await refresh_all_admin_caches(bot)
        except Exception as e:
            print(f"Admin cache refresh me error: {e}")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


async def get_all_cached_admins() -> list:
    return [doc async for doc in admin_cache_col.find({})]


async def get_cached_admins(chat_id: int):
    return await admin_cache_col.find_one({"_id": chat_id})
