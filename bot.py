import asyncio
import os
import time

import aiohttp
from pyrogram import Client, filters, StopPropagation
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter, ChatType, MessageEntityType
from pyrogram.errors import FloodWait
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPrivileges, ChatPermissions,
)
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality
from pytgcalls.types.stream import StreamEnded

from config import (
    API_ID, API_HASH, BOT_TOKEN, SESSION_STRING, DOWNLOAD_DIR,
    BOT_NAME, OWNER_ID, SUPPORT_CHAT, UPDATE_CHANNEL,
)
from utils.downloader import download_mp3, download_for_vc, download_video_for_vc
from queue_manager import get_queue, add_to_queue, pop_next, clear_queue
from sudo import get_sudo_users, add_sudo, remove_sudo
from gban import get_gban_list, is_gbanned, add_gban, remove_gban
from chat_settings import get_settings, set_setting
from warnings_store import add_warning, get_warnings, reset_warnings, MAX_WARNINGS
from playlist_store import add_to_playlist, get_playlist, remove_from_playlist, clear_playlist
from now_playing import (
    now_playing, format_time, render_progress_bar, get_elapsed, new_state,
    reset_timer, clear_state,
)
from help_menu import HELP_HOME_TEXT, HELP_SECTIONS, help_home_keyboard, help_section_keyboard
from keep_alive import keep_alive
from user_cache import cache_user, get_cached_user
from group_admin_cache import admin_cache_loop, get_all_cached_admins, get_cached_admins
from games import new_puzzle, check_answer, cancel_game, add_score, score
from game_coins import get_coins, add_coins, top_coins, mark_game_user_started, has_started_in_dm

bot = Client("blackberry_music", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call_py = PyTgCalls(assistant)


async def is_sudo(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in await get_sudo_users()


async def cache_target_by_id(target_id: int, reason: str):
    """Kisi moderation action (warn/ban/mute/kick/sudo) ka target bane user ka
    naam/username cache karta hai — sirf jab wo explicitly bot ki kisi
    action ka target bana ho, koi passive/bulk tracking nahi."""
    try:
        user = await bot.get_users(target_id)
        await cache_user(user, reason=reason)
    except Exception:
        pass


def main_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❓ Help", callback_data="help_main")],
            [InlineKeyboardButton("👑 Owner", url=f"tg://user?id={OWNER_ID}")],
            [
                InlineKeyboardButton("💬 Support Chat", url=SUPPORT_CHAT),
                InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL),
            ],
        ]
    )


def start_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{bot.me.username}?startgroup=true")],
            [InlineKeyboardButton("❓ Help", callback_data="help_main")],
            [InlineKeyboardButton("👑 Owner", url=f"tg://user?id={OWNER_ID}")],
            [
                InlineKeyboardButton("💬 Support Chat", url=SUPPORT_CHAT),
                InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL),
            ],
        ]
    )


async def settings_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    s = await get_settings(chat_id)
    welcome_label = f"👋 Welcome message: {'ON ✅' if s['welcome'] else 'OFF ❌'}"
    clean_label = f"🧹 Clean service msgs: {'ON ✅' if s['clean_service'] else 'OFF ❌'}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(welcome_label, callback_data="setting_toggle_welcome")],
            [InlineKeyboardButton(clean_label, callback_data="setting_toggle_clean_service")],
            [InlineKeyboardButton("✅ Done", callback_data="setting_close")],
        ]
    )


async def set_bot_name():
    """Sets the bot's display name via the Bot API (setMyName) - but only if it's
    not already correct, so repeated restarts/redeploys don't burn through
    Telegram's rate limit on this endpoint (that's what the 429 in your logs is)."""
    try:
        async with aiohttp.ClientSession() as session:
            get_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMyName"
            async with session.post(get_url) as resp:
                current = await resp.json()
            if current.get("ok") and current.get("result", {}).get("name") == BOT_NAME:
                return  # already correct, don't waste a rate-limited call

            set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyName"
            async with session.post(set_url, json={"name": BOT_NAME}) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    print(f"Bot name set nahi ho paya: {data}")
    except Exception as e:
        print(f"Bot name set karte waqt error: {e}")


async def try_self_promote(chat_id: int, message: Message = None) -> bool:
    """Bot khud ko admin banane ki koshish karta hai, using the assistant account
    (kaam karega sirf agar assistant us group me pehle se admin hai aur uske paas
    'Add New Admins' permission hai)."""
    try:
        await assistant.promote_chat_member(
            chat_id,
            bot.me.id,
            privileges=ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
            ),
        )
        if message:
            await message.reply_text(
                f"✅ Maine khud ko admin bana liya! **{BOT_NAME}** ab full power ke saath ready hai."
            )
        return True
    except Exception:
        if message:
            await message.reply_text(
                "❌ Khud ko admin nahi bana paya.\n\n"
                "Iske liye assistant account is group me admin hona chahiye, "
                "aur uske paas **'Add New Admins'** permission honi chahiye. "
                "Ya phir mujhe manually **Admin** bana do."
            )
        return False


async def is_group_admin(chat_id: int, user_id: int) -> bool:
    """Owner/sudo hamesha 'admin power' rakhte hain (self admin), chahe Telegram
    group me unhe actually admin banaya gaya ho ya nahi."""
    if await is_sudo(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


# ---------- Interaction-based user cache: sirf jab koi user bot ka koi command chalaye ----------
# (bulk/passive tracking nahi — sirf wahi log jo bot se directly interact karte hain)
@bot.on_message(filters.regex(r"^/\w+"), group=-5)
async def cache_command_user(_, message: Message):
    if message.from_user:
        await cache_user(message.from_user, reason="used a command")


@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        await mark_game_user_started(message.from_user.id)
        await message.reply_text(
            f"✨ **Welcome, {message.from_user.mention}!** ✨\n\n"
            f"Main hu **{BOT_NAME}** — tumhara personal music aur video companion. 🎶\n\n"
            "🎧 **Group voice chat** me live gaana ya video stream kar sakta hu\n"
            "🔗 **YouTube link** ya naam, dono se chalega\n"
            "↩️ Kisi **audio/video message** par reply karke bhi VC me chala sakta hu\n"
            "🎵 DM me `/song <name>` se MP3 le sakte ho\n"
            "🎮 DM me `/start` karke group me word games khelo aur **coins jeeto**\n"
            "🏆 Game winner ko **300 coins** milenge; `/topcoins` se leaderboard dekho\n"
            "🛠 Group management (mute, ban, warn, settings) bhi sambhal sakta hu\n\n"
            "Neeche **❓ Help** dabao poori command list ke liye, ya mujhe apne group me add karo! 👇",
            reply_markup=start_buttons(),
        )
    else:
        await message.reply_text(
            f"Namaste! Main **{BOT_NAME}** hu.\n\n"
            "**Group voice chat me gaana/video bajane ke liye:**\n"
            "/play <naam/link> - VC me audio stream karo\n"
            "/vplay <naam/link> - VC me video stream karo\n"
            "/pause /resume /skip /stop - playback control\n"
            "/queue - queue dekho\n\n"
            "**Direct MP3 chahiye to:**\n"
            "/song <song name> - MP3 file bhej dunga\n\n"
            "Poori list ke liye niche **❓ Help** dabao, ya /help bhejo.",
            reply_markup=main_buttons(),
        )


@bot.on_message(filters.command("help"))
async def help_cmd(_, message: Message):
    await message.reply_text(HELP_HOME_TEXT, reply_markup=help_home_keyboard())


@bot.on_message(filters.command("ping"))
async def ping_cmd(_, message: Message):
    start = time.monotonic()
    sent = await message.reply_text("🏓 Pinging...")
    latency_ms = (time.monotonic() - start) * 1000
    await sent.edit_text(
        f"🏓 **Pong!**\n"
        f"⏱ Latency: `{latency_ms:.2f} ms`\n"
        f"🟢 Status: **Online**"
    )


@bot.on_callback_query(filters.regex(r"^help_"))
async def help_callback(_, query: CallbackQuery):
    action = query.data.split("_", 1)[1]
    if action == "main":
        await query.message.edit_text(HELP_HOME_TEXT, reply_markup=help_home_keyboard())
    elif action == "close":
        await query.message.delete()
    elif action in HELP_SECTIONS:
        await query.message.edit_text(HELP_SECTIONS[action], reply_markup=help_section_keyboard())
    await query.answer()


@bot.on_callback_query(filters.regex(r"^setting_"))
async def settings_callback(_, query: CallbackQuery):
    chat_id = query.message.chat.id
    if not await is_group_admin(chat_id, query.from_user.id):
        return await query.answer("Sirf group admins ya sudo users hi settings badal sakte hain.", show_alert=True)

    if query.data == "setting_close":
        await query.message.delete()
        return await query.answer()

    key = query.data.replace("setting_toggle_", "")
    current = (await get_settings(chat_id)).get(key, False)
    await set_setting(chat_id, key, not current)
    await query.message.edit_reply_markup(await settings_keyboard(chat_id))
    await query.answer("Updated ✅")


# ---------- Jab bot khud kisi group me add ho: self admin power try karo ----------
# ---------- VIP welcome: jab owner/sudo kisi group me join kare jaha bot pehle se hai ----------
@bot.on_message(filters.new_chat_members)
async def new_members_handler(_, message: Message):
    settings = await get_settings(message.chat.id)
    for member in message.new_chat_members:
        if member.id == bot.me.id:
            await try_self_promote(message.chat.id, message)
            continue
        if await is_gbanned(member.id):
            try:
                await bot.ban_chat_member(message.chat.id, member.id)
                await message.reply_text(f"🔨 `{member.id}` globally banned hai, turant kick kar diya.")
            except Exception:
                pass
            continue
        if await is_sudo(member.id) and settings["welcome"]:
            role = "Owner" if member.id == OWNER_ID else "Sudo User"
            await message.reply_text(
                f"👑 **{role} entry ho gayi!**\n\n"
                f"Welcome {member.mention}, **{BOT_NAME}** aapki seva me hazir hai. 🎶",
                reply_markup=main_buttons(),
            )


# ---------- Clean service messages (join/leave/pin notices) if enabled for the group ----------
@bot.on_message(filters.service & filters.group, group=1)
async def clean_service_handler(_, message: Message):
    if (await get_settings(message.chat.id)).get("clean_service"):
        try:
            await message.delete()
        except Exception:
            pass


# ---------- Owner/Sudo self-promote: apne aap ko is chat me admin banao ----------
@bot.on_message(filters.command(["selfpromote", "promoteme"]) & filters.group)
async def selfpromote_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    privileges = ChatPrivileges(
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_invite_users=True,
        can_pin_messages=True,
    )

    # Bot ya assistant, jiske paas bhi promote karne ki permission hai use try karo
    for client in (bot, assistant):
        try:
            await client.promote_chat_member(chat_id, user_id, privileges=privileges)
            return await message.reply_text(
                f"✅ {message.from_user.mention} ko admin bana diya gaya."
            )
        except Exception:
            continue

    await message.reply_text(
        "❌ Promote nahi kar paya.\n\n"
        "Na bot aur na assistant ke paas is group me 'Add New Admins' permission hai. "
        "Pehle in me se kisi ek ko wo permission do."
    )


# ---------- Manual self-admin trigger (owner/sudo only) ----------
@bot.on_message(filters.command("selfadmin") & filters.group)
async def selfadmin_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")
    await try_self_promote(message.chat.id, message)


SUDO_TARGET_USAGE_HINT = (
    "Kise sudo list me manage karna hai?\n"
    "- Kisi user ke message par **reply** karke command bhejo\n"
    "- Ya use **tag** karo\n"
    "- Ya **@username** likho\n"
    "- Ya uska **user_id** likho"
)


# ---------- Sudo management (owner only) ----------
@bot.on_message(filters.command("addsudo") & filters.user(OWNER_ID))
async def addsudo_cmd(_, message: Message):
    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(SUDO_TARGET_USAGE_HINT)
    if target_id == OWNER_ID:
        return await message.reply_text("Owner pehle se hi sabse upar hai, alag se sudo add karne ki zaroorat nahi. 😉")
    if target_id in await get_sudo_users():
        return await message.reply_text(f"{target_mention} pehle se hi sudo user hai.")
    await add_sudo(target_id)
    await cache_target_by_id(target_id, "added as sudo")
    await message.reply_text(f"✅ {target_mention} ab sudo user hai.")


@bot.on_message(filters.command("delsudo") & filters.user(OWNER_ID))
async def delsudo_cmd(_, message: Message):
    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(SUDO_TARGET_USAGE_HINT)
    if target_id == OWNER_ID:
        return await message.reply_text("Owner ko sudo list se hataya nahi ja sakta.")
    if target_id not in await get_sudo_users():
        return await message.reply_text(f"{target_mention} sudo list me hai hi nahi.")
    await remove_sudo(target_id)
    await message.reply_text(f"✅ {target_mention} ab sudo nahi hai.")


@bot.on_message(filters.command("sudolist"))
async def sudolist_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    async def user_button(uid: int, icon: str) -> InlineKeyboardButton:
        """Naam/username wala tappable button banata hai jo tap karne par
        seedha us user ke account/chat par le jata hai (tg://user deep link)."""
        try:
            user = await bot.get_users(uid)
            if user.username:
                label = f"{icon} {user.first_name} (@{user.username})"
            else:
                label = f"{icon} {user.first_name or uid}"
        except Exception:
            label = f"{icon} User {uid}"
        return InlineKeyboardButton(label, url=f"tg://user?id={uid}")

    buttons = [[await user_button(OWNER_ID, "👑")]]
    for uid in await get_sudo_users():
        buttons.append([await user_button(uid, "🛡")])

    await message.reply_text(
        "**Sudo Users**\n\nKisi bhi naam par tap karo, seedha uske account par chale jaoge 👇",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------- Shared target resolver: reply / tag / @username / user_id ----------
async def resolve_target_and_reason(message: Message, default_reason="Koi reason nahi diya gaya"):
    """4 tarike se target user nikalta hai: reply, tag (text mention), @username, ya user_id.
    Returns (user_id, mention_text, reason) ya (None, None, None) agar kuch na mile."""
    text = message.text or ""

    # 1. Reply karke
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        parts = text.split(None, 1)
        reason = parts[1] if len(parts) > 1 else default_reason
        return target.id, target.mention, reason

    # 2. Message entities: tag (bina username wale user ko mention karna) ya @username
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                target = entity.user
                reason = text[entity.offset + entity.length:].strip() or default_reason
                return target.id, target.mention, reason
            if entity.type == MessageEntityType.MENTION:
                username = text[entity.offset: entity.offset + entity.length]
                try:
                    user = await bot.get_users(username)
                except Exception:
                    return None, None, None
                reason = text[entity.offset + entity.length:].strip() or default_reason
                return user.id, user.mention, reason

    # 3. Plain command argument: @username ya numeric user_id
    if len(message.command) > 1:
        arg = message.command[1]
        rest = text.split(None, 2)
        reason = rest[2] if len(rest) > 2 else default_reason
        if arg.startswith("@"):
            try:
                user = await bot.get_users(arg)
            except Exception:
                return None, None, None
            return user.id, user.mention, reason
        try:
            uid = int(arg)
            return uid, f"`{uid}`", reason
        except ValueError:
            return None, None, None

    return None, None, None


async def get_media_from_reply(message: Message):
    """Reply kiye gaye message se audio/video media download karta hai (agar ho to).
    Returns (path, title, kind, duration) - kind is 'audio' ya 'video'. Kuch na mile to (None, None, None, None)."""
    reply = message.reply_to_message
    if not reply:
        return None, None, None, None

    media = reply.audio or reply.voice or reply.video or reply.video_note or reply.document
    if not media:
        return None, None, None, None

    if reply.video or reply.video_note:
        kind = "video"
    elif reply.document and (reply.document.mime_type or "").startswith("video"):
        kind = "video"
    else:
        kind = "audio"

    title = getattr(media, "file_name", None) or (reply.caption or None) or "Replied media"
    duration = getattr(media, "duration", None)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        path = await reply.download(file_name=f"{DOWNLOAD_DIR}/")
    except Exception:
        return None, None, None, None
    return path, title, kind, duration


TARGET_USAGE_HINT = (
    "Kise target karna hai?\n"
    "- Kisi user ke message par **reply** karke command bhejo\n"
    "- Ya use **tag** karo\n"
    "- Ya **@username** likho\n"
    "- Ya uska **user_id** likho"
)


# ---------- Local ban/unban (is group tak seemit — group admins ya sudo/owner) ----------
@bot.on_message(filters.command("ban") & filters.group)
async def ban_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, reason = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if target_id == OWNER_ID or await is_sudo(target_id):
        return await message.reply_text("Owner ya sudo users ko ban nahi kiya ja sakta.")

    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await cache_target_by_id(target_id, "banned")
        await message.reply_text(f"🔨 {target_mention} is group se ban kar diya gaya.\nReason: {reason}")
    except Exception as e:
        await message.reply_text(f"Ban nahi kar paya: {e}")


@bot.on_message(filters.command("unban") & filters.group)
async def unban_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)

    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.reply_text(f"✅ {target_mention} is group me unban kar diya gaya.")
    except Exception as e:
        await message.reply_text(f"Unban nahi kar paya: {e}")


# ---------- Global ban (owner/sudo only) ----------
@bot.on_message(filters.command("gban"))
async def gban_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    target_id, target_mention, reason = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if target_id == OWNER_ID or await is_sudo(target_id):
        return await message.reply_text("Owner ya sudo users ko gban nahi kiya ja sakta.")

    await add_gban(target_id, reason)

    banned_in = 0
    try:
        async for dialog in bot.get_dialogs():
            if dialog.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                try:
                    await bot.ban_chat_member(dialog.chat.id, target_id)
                    banned_in += 1
                except Exception:
                    continue
    except Exception:
        pass

    await message.reply_text(
        f"🔨 {target_mention} ko globally ban kar diya gaya.\n"
        f"Reason: {reason}\n"
        f"Bot ke {banned_in} group(s) me turant ban kiya gaya — baaki groups me jaate hi turant ban ho jayega."
    )


@bot.on_message(filters.command("ungban"))
async def ungban_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if not await is_gbanned(target_id):
        return await message.reply_text("Ye user gbanned nahi hai.")

    await remove_gban(target_id)

    unbanned_in = 0
    try:
        async for dialog in bot.get_dialogs():
            if dialog.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                try:
                    await bot.unban_chat_member(dialog.chat.id, target_id)
                    unbanned_in += 1
                except Exception:
                    continue
    except Exception:
        pass

    await message.reply_text(
        f"✅ {target_mention} ko gban se hata diya gaya, {unbanned_in} group(s) me unban bhi kar diya."
    )


@bot.on_message(filters.command("gbanlist"))
async def gbanlist_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")
    data = await get_gban_list()
    if not data:
        return await message.reply_text("Koi bhi globally banned nahi hai abhi.")
    text = "\n".join(f"`{uid}` - {reason}" for uid, reason in data.items())
    await message.reply_text(f"🔨 Globally banned users:\n{text}")


# ---------- /broadcast: owner/sudo hi kar sakte hain ----------
# Groups me bheja gaya message pin bhi kiya jata hai; personal (DM) sirf un users ko
# jaate hai jinhone khud bot se private chat shuru ki hai — bot API se kisi aise
# user ko DM nahi bheja ja sakta jisne bot ko kabhi start hi nahi kiya, isliye ye
# feature khud-b-khud sirf "opted-in" logo tak seemit rehta hai.
@bot.on_message(filters.command("broadcast"))
async def broadcast_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    source = message.reply_to_message
    text = None
    mode = "all"
    if not source:
        if len(message.command) < 2:
            return await message.reply_text(
                "Kya broadcast karna hai?\n"
                "- Kisi message (text/photo/video/document) par **reply** karke `/broadcast` bhejo\n"
                "- `/broadcast <text>` = Groups + DMs\n"
                "- `/broadcast groups <text>` = sirf Groups\n"
                "- `/broadcast dm <text>` = sirf personal DMs\n"
                "- `/broadcast all <text>` = Groups + DMs"
            )
        first = message.command[1].lower()
        if first in ("groups", "group"):
            mode = "groups"
            text = message.text.split(None, 2)[2] if len(message.command) > 2 else None
        elif first in ("dm", "dms", "users", "user", "private"):
            mode = "dm"
            text = message.text.split(None, 2)[2] if len(message.command) > 2 else None
        elif first == "all":
            mode = "all"
            text = message.text.split(None, 2)[2] if len(message.command) > 2 else None
        else:
            text = message.text.split(None, 1)[1]
        if not text:
            return await message.reply_text("Broadcast text missing hai. Example: `/broadcast all Hello everyone!`")
    else:
        # Reply-based broadcast defaults to both groups and personal DMs.
        if len(message.command) > 1:
            mode_arg = message.command[1].lower()
            if mode_arg in ("groups", "group"):
                mode = "groups"
            elif mode_arg in ("dm", "dms", "users", "user", "private"):
                mode = "dm"
            elif mode_arg == "all":
                mode = "all"

    status = await message.reply_text("📢 Broadcast shuru ho raha hai, thoda time lagega...")

    group_sent = group_failed = group_pinned = 0
    dm_sent = dm_failed = 0

    async for dialog in bot.get_dialogs():
        chat = dialog.chat
        is_group = chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
        is_private = chat.type == ChatType.PRIVATE

        if not (is_group or is_private):
            continue
        if mode == "groups" and not is_group:
            continue
        if mode == "dm" and not is_private:
            continue

        for attempt in range(2):  # ek retry FloodWait ke baad
            try:
                if source:
                    sent = await source.copy(chat.id)
                else:
                    sent = await bot.send_message(chat.id, text)

                if is_group:
                    group_sent += 1
                    try:
                        await bot.pin_chat_message(chat.id, sent.id)
                        group_pinned += 1
                    except Exception:
                        pass  # bot ke paas pin permission nahi hai is group me
                else:
                    dm_sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception:
                if is_group:
                    group_failed += 1
                else:
                    dm_failed += 1
                break

        await asyncio.sleep(0.05)  # thoda gap, taaki flood-limit na lage

    await status.edit_text(
        "📢 **Broadcast complete**\n\n"
        f"🏘 Groups: {group_sent} sent, {group_pinned} pinned, {group_failed} failed\n"
        f"👤 Personal chats: {dm_sent} sent, {dm_failed} failed\n\n"
        "_(Personal chats me sirf un users ko bheja gaya jinhone khud bot ko pehle start kiya tha.)_"
    )


# ---------- Word games ----------
async def game_access_ok(message: Message) -> bool:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text("🎮 Games sirf **groups/supergroups** me khele ja sakte hain.\n\nPehle mujhe DM me `/start` karo, phir mujhe group me use karke game start karo.")
        return False
    if not message.from_user or not await has_started_in_dm(message.from_user.id):
        await message.reply_text("🔐 Game khelne ke liye pehle mujhe **DM me /start** karo. Uske baad isi group me game khel sakte ho.")
        return False
    return True

@bot.on_message(filters.command(["wordpuzzle", "wordgame", "wp"]))
async def word_puzzle_cmd(_, message: Message):
    if not await game_access_ok(message):
        return
    difficulty = message.command[1].lower() if len(message.command) > 1 else "medium"
    if difficulty not in ("easy", "medium", "hard"):
        return await message.reply_text("Use: `/wordpuzzle easy`, `/wordpuzzle medium` ya `/wordpuzzle hard`")
    text = new_puzzle(message.chat.id, "word", difficulty)
    await message.reply_text(text)


@bot.on_message(filters.command(["missing", "missingletter", "missingword"]))
async def missing_letter_cmd(_, message: Message):
    if not await game_access_ok(message):
        return
    difficulty = message.command[1].lower() if len(message.command) > 1 else "medium"
    if difficulty not in ("easy", "medium", "hard"):
        return await message.reply_text("Use: `/missing easy`, `/missing medium` ya `/missing hard`")
    text = new_puzzle(message.chat.id, "missing", difficulty)
    await message.reply_text(text)


@bot.on_message(filters.command(["gamecancel", "cancelgame"]))
async def game_cancel_cmd(_, message: Message):
    if cancel_game(message.chat.id):
        await message.reply_text("🛑 Current word game cancel kar diya.")
    else:
        await message.reply_text("Abhi koi active word game nahi hai.")


@bot.on_message(filters.command(["gamescore", "wordscore"]))
async def game_score_cmd(_, message: Message):
    coins = await get_coins(message.from_user.id)
    await message.reply_text(
        f"🏆 {message.from_user.mention}\n"
        f"⭐ Game points: **{score(message.from_user.id)}**\n"
        f"🪙 Coins: **{coins}**"
    )


@bot.on_message(filters.command(["coins", "balance"]))
async def coins_cmd(_, message: Message):
    coins = await get_coins(message.from_user.id)
    await message.reply_text(f"🪙 {message.from_user.mention} ke paas **{coins} coins** hain.")


@bot.on_message(filters.command(["topcoins", "coinleaderboard", "cointop"]))
async def top_coins_cmd(_, message: Message):
    rows = await top_coins(10)
    if not rows:
        return await message.reply_text("🏆 Abhi coin leaderboard empty hai. Game khelo aur 300 coins jeeto!")

    lines = ["🏆 **TOP COIN LEADERBOARD**\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows, 1):
        uid = int(row["_id"])
        coins = int(row.get("coins", 0))
        try:
            user = await bot.get_users(uid)
            name = user.first_name or str(uid)
            label = user.mention
        except Exception:
            name = str(uid)
            label = f"[{name}](tg://user?id={uid})"
        prefix = medals[i - 1] if i <= 3 else f"**{i}.**"
        lines.append(f"{prefix} {label} — **{coins} 🪙**")
    await message.reply_text("\n".join(lines))


@bot.on_message(filters.text & ~filters.command(["start", "help", "ping", "broadcast", "wordpuzzle", "wordgame", "wp", "missing", "missingletter", "missingword", "gamecancel", "cancelgame", "gamescore", "wordscore"]), group=0)
async def word_game_answer(_, message: Message):
    if not message.from_user or not (message.text or "").strip():
        return
    result = check_answer(message.chat.id, message.text.strip())
    if not result:
        return
    if result["status"] == "timeout":
        await message.reply_text(f"⏰ Time up! Correct answer tha **{result['answer']}**.\n\nNaya game `/wordpuzzle` ya `/missing` se start karo.")
    elif result["status"] == "correct":
        total = add_score(message.from_user.id, result["points"])
        coins = await add_coins(message.from_user.id, 300)
        await message.reply_text(
            f"🎉 **Winner!** {message.from_user.mention}\n"
            f"✅ Answer: **{result['answer']}**\n"
            f"⭐ +{result['points']} points | Total: **{total}**\n"
            f"🪙 **+300 coins** | Coin balance: **{coins}**\n\n"
            f"🏆 `/topcoins` se leaderboard dekho."
        )


# ---------- Global ban enforcement: har group me automatically apply ----------
@bot.on_message(filters.group, group=-1)
async def gban_enforcer(_, message: Message):
    if message.from_user and await is_gbanned(message.from_user.id):
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
        except Exception:
            pass
        raise StopPropagation


# ---------- /kick: remove user from group (not a permanent ban) ----------
@bot.on_message(filters.command("kick") & filters.group)
async def kick_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, reason = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if target_id == OWNER_ID or await is_sudo(target_id):
        return await message.reply_text("Owner ya sudo users ko kick nahi kiya ja sakta.")

    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await bot.unban_chat_member(message.chat.id, target_id)
        await cache_target_by_id(target_id, "kicked")
        await message.reply_text(f"👢 {target_mention} ko group se kick kar diya gaya.\nReason: {reason}")
    except Exception as e:
        await message.reply_text(f"Kick nahi kar paya: {e}")


# ---------- /mute, /unmute ----------
@bot.on_message(filters.command("mute") & filters.group)
async def mute_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, reason = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if target_id == OWNER_ID or await is_sudo(target_id):
        return await message.reply_text("Owner ya sudo users ko mute nahi kiya ja sakta.")

    try:
        await bot.restrict_chat_member(message.chat.id, target_id, ChatPermissions())
        await cache_target_by_id(target_id, "muted")
        await message.reply_text(f"🔇 {target_mention} ko mute kar diya gaya.\nReason: {reason}")
    except Exception as e:
        await message.reply_text(f"Mute nahi kar paya: {e}")


@bot.on_message(filters.command("unmute") & filters.group)
async def unmute_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_send_polls=True,
                can_add_web_page_previews=True,
            ),
        )
        await message.reply_text(f"🔊 {target_mention} ko unmute kar diya gaya.")
    except Exception as e:
        await message.reply_text(f"Unmute nahi kar paya: {e}")


# ---------- /pin, /unpin ----------
@bot.on_message(filters.command("pin") & filters.group)
async def pin_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    if not message.reply_to_message:
        return await message.reply_text("Jis message ko pin karna hai, uspar reply karke /pin bhejo.")
    try:
        await message.reply_to_message.pin()
        await message.reply_text("📌 Pin kar diya.")
    except Exception as e:
        await message.reply_text(f"Pin nahi kar paya: {e}")


@bot.on_message(filters.command("unpin") & filters.group)
async def unpin_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    try:
        if message.reply_to_message:
            await message.reply_to_message.unpin()
        else:
            await bot.unpin_all_chat_messages(message.chat.id)
        await message.reply_text("📌 Unpin kar diya.")
    except Exception as e:
        await message.reply_text(f"Unpin nahi kar paya: {e}")


# ---------- /purge: reply se lekar is command tak sab messages delete ----------
@bot.on_message(filters.command("purge") & filters.group)
async def purge_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    if not message.reply_to_message:
        return await message.reply_text("Jaha se purge shuru karna hai, uss message par reply karke /purge bhejo.")

    ids = list(range(message.reply_to_message.id, message.id + 1))
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        try:
            await bot.delete_messages(message.chat.id, batch)
        except Exception:
            pass

    note = await bot.send_message(message.chat.id, f"🧹 Purge kar diya ({len(ids)} messages tak).")
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


# ---------- Warning system: 3 warnings = auto-ban ----------
@bot.on_message(filters.command("warn") & filters.group)
async def warn_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, reason = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)
    if target_id == OWNER_ID or await is_sudo(target_id):
        return await message.reply_text("Owner ya sudo users ko warn nahi kiya ja sakta.")

    await cache_target_by_id(target_id, "warned")
    count = await add_warning(message.chat.id, target_id, reason)
    if count >= MAX_WARNINGS:
        await reset_warnings(message.chat.id, target_id)
        try:
            await bot.ban_chat_member(message.chat.id, target_id)
            await message.reply_text(
                f"🔨 {target_mention} ko {MAX_WARNINGS} warnings ke baad ban kar diya gaya."
            )
        except Exception as e:
            await message.reply_text(f"Max warnings ho gaye lekin ban nahi kar paya: {e}")
    else:
        await message.reply_text(
            f"⚠️ {target_mention} ko warn kiya gaya ({count}/{MAX_WARNINGS}).\nReason: {reason}"
        )


@bot.on_message(filters.command("warnings") & filters.group)
async def warnings_cmd(_, message: Message):
    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        target_id, target_mention = message.from_user.id, message.from_user.mention

    entries = await get_warnings(message.chat.id, target_id)
    if not entries:
        return await message.reply_text(f"{target_mention} ke paas koi warning nahi hai.")
    text = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(entries))
    await message.reply_text(f"⚠️ {target_mention} ke warnings ({len(entries)}/{MAX_WARNINGS}):\n{text}")


@bot.on_message(filters.command(["resetwarn", "resetwarns"]) & filters.group)
async def resetwarn_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        return await message.reply_text(TARGET_USAGE_HINT)

    await reset_warnings(message.chat.id, target_id)
    await message.reply_text(f"✅ {target_mention} ke warnings reset kar diye gaye.")


# ---------- /admins: group ke admins list karo ----------
@bot.on_message(filters.command("admins") & filters.group)
async def admins_cmd(_, message: Message):
    try:
        lines = []
        async for member in bot.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
            role = "👑 Owner" if member.status == ChatMemberStatus.OWNER else "🛠 Admin"
            lines.append(f"{role} — {member.user.mention}")
        if not lines:
            return await message.reply_text("Admins ki list nahi mil payi.")
        await message.reply_text("**Group Admins:**\n" + "\n".join(lines))
    except Exception as e:
        await message.reply_text(f"Admins list nahi la paya: {e}")


# ---------- /groupadmins: sab groups ke admins ka 10-minute-refresh cache dikhata hai ----------
@bot.on_message(filters.command(["groupadmins", "allgroupadmins"]))
async def groupadmins_cmd(_, message: Message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Ye command sirf owner ya sudo users use kar sakte hain.")

    docs = await get_all_cached_admins()
    if not docs:
        return await message.reply_text(
            "Abhi tak koi admin cache nahi bana — pehla refresh 10 minute ke andar ho jayega."
        )

    lines = []
    for doc in docs:
        updated = doc.get("updated_at")
        stamp = updated.strftime("%Y-%m-%d %H:%M UTC") if updated else "?"
        admin_names = ", ".join(a.get("name") or str(a["id"]) for a in doc.get("admins", []))
        lines.append(f"**{doc.get('title', doc['_id'])}**\n{admin_names or 'koi admin nahi mila'}\n_updated: {stamp}_")

    await message.reply_text("👥 **Cached Group Admins** (har 10 min me refresh hota hai):\n\n" + "\n\n".join(lines))


# ---------- /whois: on-demand kisi ek user ka current info dekho ----------
@bot.on_message(filters.command(["whois", "userinfo"]))
async def whois_cmd(_, message: Message):
    if message.chat.type != ChatType.PRIVATE and not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")

    target_id, target_mention, _ = await resolve_target_and_reason(message)
    if target_id is None:
        target_id, target_mention = message.from_user.id, message.from_user.mention

    try:
        user = await bot.get_users(target_id)
    except Exception as e:
        return await message.reply_text(f"User ki info nahi mil payi: {e}")

    lines = [
        f"👤 **{user.first_name or ''} {user.last_name or ''}**".strip(),
        f"🆔 `{user.id}`",
        f"🔗 Username: @{user.username}" if user.username else "🔗 Username: nahi hai",
        f"👑 Sudo: {'Haan' if await is_sudo(user.id) else 'Nahi'}",
        f"🔨 Globally banned: {'Haan' if await is_gbanned(user.id) else 'Nahi'}",
    ]

    cached = await get_cached_user(user.id)
    if cached and cached.get("updated_at"):
        lines.append(
            f"🕒 Last bot interaction: {cached['updated_at'].strftime('%Y-%m-%d %H:%M UTC')} "
            f"({cached.get('last_reason', 'unknown')})"
        )

    await message.reply_text("\n".join(lines))


# ---------- /settings: welcome message & clean-service-messages toggle ----------
@bot.on_message(filters.command("settings") & filters.group)
async def settings_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    await message.reply_text(
        "⚙️ **Group Settings**\n\nNiche button dabakar on/off karo.",
        reply_markup=await settings_keyboard(message.chat.id),
    )


# ---------- /song: direct mp3 download & send ----------
@bot.on_message(filters.command("song"))
async def song_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Gaane ka naam bhi likho: /song tera hone laga hu")

    query = message.text.split(None, 1)[1]
    msg = await message.reply_text(f"Dhoondh raha hu: {query} ...")
    path = None
    try:
        path, title = await asyncio.to_thread(download_mp3, query)
        await msg.edit_text(f"Bhej raha hu: {title}")
        await message.reply_audio(path, title=title)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Error aaya: {e}")
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# ---------- /play: voice chat me audio streaming ----------
@bot.on_message(filters.command("play") & filters.group)
async def play_cmd(_, message: Message):
    chat_id = message.chat.id
    requested_by = message.from_user.mention if message.from_user else "Unknown"

    reply_path, reply_title, reply_kind, reply_duration = await get_media_from_reply(message)
    if reply_path:
        path, title, kind, duration, url = reply_path, reply_title, "audio", reply_duration, None
        msg = await message.reply_text(f"Reply kiye gaye media ko queue me daal raha hu: {title}")
    else:
        if len(message.command) < 2:
            return await message.reply_text(
                "Gaane ka naam ya YouTube link likho: /play kesariya\n"
                "Ya kisi audio/video message par reply karke /play bhejo."
            )
        query = message.text.split(None, 1)[1]
        msg = await message.reply_text(f"Dhoondh raha hu: {query} ...")
        try:
            path, title, duration, url = await asyncio.to_thread(download_for_vc, query)
        except Exception as e:
            return await msg.edit_text(f"Download nahi hua: {e}")
        kind = "audio"

    queue = get_queue(chat_id)
    add_to_queue(chat_id, {
        "path": path, "title": title, "kind": kind, "duration": duration,
        "url": url, "requested_by": requested_by,
    })

    if len(queue) > 1:
        # already something playing, this one just got added above
        return await msg.edit_text(f"Queue me add ho gaya: {title}")

    await start_playback(chat_id, msg)


# ---------- /vplay: voice chat me video (audio ke saath) streaming ----------
@bot.on_message(filters.command(["vplay", "playvideo"]) & filters.group)
async def vplay_cmd(_, message: Message):
    chat_id = message.chat.id
    requested_by = message.from_user.mention if message.from_user else "Unknown"

    reply_path, reply_title, reply_kind, reply_duration = await get_media_from_reply(message)
    if reply_path:
        path, title, kind, duration, url = reply_path, reply_title, "video", reply_duration, None
        msg = await message.reply_text(f"Reply kiye gaye media ko video ke saath queue me daal raha hu: {title}")
    else:
        if len(message.command) < 2:
            return await message.reply_text(
                "Video/gaane ka naam ya YouTube link likho: /vplay kesariya\n"
                "Ya kisi audio/video message par reply karke /vplay bhejo."
            )
        query = message.text.split(None, 1)[1]
        msg = await message.reply_text(f"Video dhoondh raha hu: {query} ...")
        try:
            path, title, duration, url = await asyncio.to_thread(download_video_for_vc, query)
        except Exception as e:
            return await msg.edit_text(f"Download nahi hua: {e}")
        kind = "video"

    queue = get_queue(chat_id)
    add_to_queue(chat_id, {
        "path": path, "title": title, "kind": kind, "duration": duration,
        "url": url, "requested_by": requested_by,
    })

    if len(queue) > 1:
        return await msg.edit_text(f"Queue me add ho gaya (video): {title}")

    await start_playback(chat_id, msg)


def _build_stream(item: dict):
    if item["kind"] == "video":
        return MediaStream(item["path"], AudioQuality.HIGH, VideoQuality.SD_480p)
    return MediaStream(item["path"], video_flags=MediaStream.Flags.IGNORE)


def render_now_playing_card(chat_id):
    state = now_playing[chat_id]
    elapsed = get_elapsed(chat_id)
    duration = state["duration"]
    bar = render_progress_bar(elapsed, duration)
    icon = "🎥" if state["kind"] == "video" else "🎵"
    play_icon = "▶️" if state["paused"] else "⏸️"

    text = (
        "🔁 **Started Streaming** |\n\n"
        f"{icon} **Title:** {state['title']}\n"
        f"⏱ **Duration:** {format_time(duration)} minutes\n"
        f"🙋 **Requested by:** {state['requested_by']}\n\n"
        f"`{format_time(elapsed)}` {bar} `{format_time(duration)}`"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(play_icon, callback_data="np_playpause"),
            InlineKeyboardButton("🔁", callback_data="np_replay"),
            InlineKeyboardButton("⏭️", callback_data="np_skip"),
            InlineKeyboardButton("⏹️", callback_data="np_stop"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="np_close"),
            InlineKeyboardButton("➕ Add to Playlist", callback_data="np_addpl"),
        ],
    ])
    return text, markup


async def start_playback(chat_id, msg=None):
    queue = get_queue(chat_id)
    if not queue:
        return
    item = queue[0]
    try:
        await call_py.play(chat_id, _build_stream(item))
    except Exception as e:
        text = (f"VC me join/play nahi ho paya: {e}\n\n"
                f"Check karo ki VC pehle se on hai aur assistant account us group me hai.")
        if msg:
            await msg.edit_text(text)
        else:
            await bot.send_message(chat_id, text)
        return

    clear_state(chat_id)  # cancel any stray progress task from a previous track
    state = new_state(item["title"], item["kind"], item.get("duration"),
                       item.get("requested_by", "Unknown"), item.get("url"))
    now_playing[chat_id] = state

    text, markup = render_now_playing_card(chat_id)
    sent = None
    if msg:
        try:
            sent = await msg.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            sent = None
    if not sent:
        sent = await bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)

    state["msg"] = sent
    state["task"] = asyncio.create_task(progress_updater(chat_id))


async def progress_updater(chat_id):
    """Edits the Now Playing card every ~15s so the progress bar keeps moving."""
    try:
        while True:
            await asyncio.sleep(15)
            state = now_playing.get(chat_id)
            if not state or not state.get("msg"):
                return
            if state["paused"]:
                continue
            text, markup = render_now_playing_card(chat_id)
            try:
                await state["msg"].edit_text(text, reply_markup=markup, disable_web_page_preview=True)
            except Exception:
                pass
    except asyncio.CancelledError:
        pass


async def _advance_or_leave(chat_id):
    """Pops the finished/skipped track, deletes its file, and moves to the next one."""
    finished = pop_next(chat_id)
    if finished and finished.get("path") and os.path.exists(finished["path"]):
        os.remove(finished["path"])

    queue = get_queue(chat_id)
    if queue:
        await start_playback(chat_id)
        return True
    else:
        clear_state(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass
        return False


@call_py.on_update()
async def stream_end_handler(_, update):
    if not isinstance(update, StreamEnded):
        return
    await _advance_or_leave(update.chat_id)


@bot.on_callback_query(filters.regex("^np_"))
async def now_playing_callback(_, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    action = cq.data.split("_", 1)[1]
    state = now_playing.get(chat_id)

    if action == "close":
        try:
            await cq.message.delete()
        except Exception:
            pass
        return await cq.answer()

    if action == "addpl":
        if not state:
            return await cq.answer("Kuch bhi chal nahi raha.", show_alert=True)
        added = await add_to_playlist(chat_id, state["title"], state.get("url"))
        if added:
            return await cq.answer(f"Playlist me add ho gaya: {state['title']}", show_alert=True)
        return await cq.answer("Playlist full hai (max 50). Kuch hatao pehle.", show_alert=True)

    if not state:
        return await cq.answer("Kuch bhi chal nahi raha.", show_alert=True)

    if not await is_group_admin(chat_id, cq.from_user.id):
        return await cq.answer("Sirf group admins ya sudo users ye control kar sakte hain.", show_alert=True)

    if action == "playpause":
        try:
            if state["paused"]:
                await call_py.resume(chat_id)
                state["paused_total"] += time.time() - state["paused_at"]
                state["paused_at"] = None
                state["paused"] = False
            else:
                await call_py.pause(chat_id)
                state["paused"] = True
                state["paused_at"] = time.time()
        except Exception as e:
            return await cq.answer(f"Error: {e}", show_alert=True)
        text, markup = render_now_playing_card(chat_id)
        await cq.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        return await cq.answer()

    if action == "replay":
        queue = get_queue(chat_id)
        if not queue:
            return await cq.answer()
        try:
            await call_py.play(chat_id, _build_stream(queue[0]))
        except Exception as e:
            return await cq.answer(f"Error: {e}", show_alert=True)
        reset_timer(state)
        text, markup = render_now_playing_card(chat_id)
        await cq.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        return await cq.answer("Replay ho raha hai.")

    if action == "skip":
        await cq.answer("Skip kar raha hu...")
        await _advance_or_leave(chat_id)
        return

    if action == "stop":
        clear_queue(chat_id)
        clear_state(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass
        try:
            await cq.message.edit_text("⏹️ Music band kar diya, queue bhi clear kar di.")
        except Exception:
            pass
        return await cq.answer()


@bot.on_message(filters.command("pause") & filters.group)
async def pause_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    chat_id = message.chat.id
    try:
        await call_py.pause(chat_id)
        state = now_playing.get(chat_id)
        if state and not state["paused"]:
            state["paused"] = True
            state["paused_at"] = time.time()
        await message.reply_text("Pause kar diya.")
    except Exception as e:
        await message.reply_text(f"Error: {e}")


@bot.on_message(filters.command("resume") & filters.group)
async def resume_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    chat_id = message.chat.id
    try:
        await call_py.resume(chat_id)
        state = now_playing.get(chat_id)
        if state and state["paused"]:
            state["paused_total"] += time.time() - state["paused_at"]
            state["paused_at"] = None
            state["paused"] = False
        await message.reply_text("Resume kar diya.")
    except Exception as e:
        await message.reply_text(f"Error: {e}")


@bot.on_message(filters.command("skip") & filters.group)
async def skip_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    chat_id = message.chat.id
    moved = await _advance_or_leave(chat_id)
    if moved:
        await message.reply_text("Next gaana laga diya.")
    else:
        await message.reply_text("Queue khali hai, VC se nikal gaya.")


@bot.on_message(filters.command("stop") & filters.group)
async def stop_cmd(_, message: Message):
    if not await is_group_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
    chat_id = message.chat.id
    clear_queue(chat_id)
    clear_state(chat_id)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await message.reply_text("Music band kar diya, queue bhi clear kar di.")


@bot.on_message(filters.command("queue") & filters.group)
async def queue_cmd(_, message: Message):
    queue = get_queue(message.chat.id)
    if not queue:
        return await message.reply_text("Queue khali hai.")
    lines = []
    for i, item in enumerate(queue):
        icon = "🎥" if item.get("kind") == "video" else "🎵"
        lines.append(f"{i + 1}. {icon} {item['title']}")
    await message.reply_text("Queue:\n" + "\n".join(lines))


# ---------- /playlist: per-chat saved playlist (Mongo-backed) ----------
@bot.on_message(filters.command("playlist") & filters.group)
async def playlist_cmd(_, message: Message):
    chat_id = message.chat.id
    args = message.text.split(None, 2)[1:] if len(message.command) > 1 else []

    if not args:
        items = await get_playlist(chat_id)
        if not items:
            return await message.reply_text(
                "Playlist khali hai. Kisi gaane ke Now Playing card par "
                "➕ **Add to Playlist** dabao usse add karne ke liye."
            )
        lines = [f"{i + 1}. {it['title']}" for i, it in enumerate(items)]
        return await message.reply_text(
            "🎶 **Playlist:**\n" + "\n".join(lines) +
            "\n\nChalane ke liye: `/playlist play <number>`"
        )

    sub = args[0].lower()

    if sub == "play":
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
        if len(args) < 2 or not args[1].isdigit():
            return await message.reply_text("Number bhi do: /playlist play 2")
        items = await get_playlist(chat_id)
        idx = int(args[1])
        if idx < 1 or idx > len(items):
            return await message.reply_text("Ye number playlist me nahi hai.")
        entry = items[idx - 1]
        if not entry.get("url"):
            return await message.reply_text("Ye entry ka source link save nahi hai, dobara /play se try karo.")
        msg = await message.reply_text(f"Dhoondh raha hu: {entry['title']} ...")
        try:
            path, title, duration, url = await asyncio.to_thread(download_for_vc, entry["url"])
        except Exception as e:
            return await msg.edit_text(f"Download nahi hua: {e}")
        requested_by = message.from_user.mention if message.from_user else "Unknown"
        queue = get_queue(chat_id)
        add_to_queue(chat_id, {
            "path": path, "title": title, "kind": "audio",
            "duration": duration, "url": url, "requested_by": requested_by,
        })
        if len(queue) > 1:
            return await msg.edit_text(f"Queue me add ho gaya: {title}")
        return await start_playback(chat_id, msg)

    if sub in ("clear", "remove") and (sub == "clear" or len(args) < 2):
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
        await clear_playlist(chat_id)
        return await message.reply_text("Playlist clear kar di.")

    if sub == "remove" and len(args) >= 2 and args[1].isdigit():
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("Ye command sirf group admins ya sudo users use kar sakte hain.")
        ok = await remove_from_playlist(chat_id, int(args[1]))
        return await message.reply_text("Hata diya." if ok else "Ye number playlist me nahi hai.")

    return await message.reply_text(
        "Commands:\n`/playlist` — list dekho\n`/playlist play <n>` — usse chalao\n"
        "`/playlist remove <n>` — usse hatao\n`/playlist clear` — poori list clear karo"
    )


async def main():
    await assistant.start()
    await bot.start()
    await call_py.start()
    await set_bot_name()
    asyncio.create_task(admin_cache_loop(assistant))
    print(f"{BOT_NAME} chalu ho gaya. Bot aur assistant dono ready hain.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    keep_alive()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
