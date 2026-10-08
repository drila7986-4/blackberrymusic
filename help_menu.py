from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

HELP_HOME_TEXT = (
    "❓ **Help Menu**\n\n"
    "Neeche category chuno, sab commands wahi mil jayenge."
)

HELP_SECTIONS = {
    "general": (
        "ℹ️ **General Commands**\n\n"
        "`/start` — Bot start karo, welcome message dekho\n"
        "`/help` — Ye help menu kholo\n"
        "`/wordpuzzle [easy|medium|hard]` — Scrambled word puzzle\n"
        "`/missing [easy|medium|hard]` — Missing-letter puzzle\n"
        "`/gamescore` — Game points aur coins dekho\n`/coins` — Apna coin balance dekho\n`/topcoins` — Top 10 coin leaderboard\n"
        "`/gamecancel` — Active game cancel karo"
    ),
    "music": (
        "🎵 **Music & Video Commands**\n\n"
        "`/play <naam/link>` — VC me audio stream karo\n"
        "`/vplay <naam/link>` — VC me video (audio ke saath) stream karo\n"
        "`/song <naam/link>` — Seedha MP3 file bhejo\n"
        "`/pause` `/resume` `/skip` `/stop` — playback control\n"
        "`/queue` — current queue dekho\n"
        "`/playlist` — saved playlist dekho/chalao (`/playlist play <n>`, `/playlist remove <n>`, `/playlist clear`)\n\n"
        "💡 Har gaane ke saath Now Playing card aur playback buttons aate hain.\n"
        "💡 Audio/video message par reply karke `/play` ya `/vplay` bhej sakte ho."
    ),
    "admin": (
        "🛠 **Group Management**\n\n"
        "`/kick` `/ban` `/unban` `/mute` `/unmute` — reply/tag/@username/user_id se\n"
        "`/pin` `/unpin` — reply kiye gaye message par\n"
        "`/purge` — reply se lekar is message tak sab delete\n"
        "`/warn` `/warnings` `/resetwarn` — warning system (3 warnings par auto-ban)\n"
        "`/admins` — group ke admins dikhata hai\n"
        "`/settings` — group settings"
    ),
    "sudo": (
        "👑 **Owner & Sudo**\n\n"
        "`/addsudo` `/delsudo` — sudo management\n"
        "`/sudolist` — sudo users\n"
        "`/gban` `/ungban` `/gbanlist` — global ban\n"
        "`/selfpromote` `/selfadmin` — admin power\n"
        "`/whois <reply/tag/@username/id>` — user info\n"
        "`/groupadmins` — cached group admins overview\n\n"
        "📢 **Broadcast**\n"
        "`/broadcast <text>` ya message par reply — Groups + personal DMs dono\n"
        "`/broadcast groups <text>` — sirf groups\n"
        "`/broadcast dm <text>` — sirf personal DMs\n"
        "`/broadcast all <text>` — Groups + DMs (default)\n\n"
        "Ye commands owner/sudo ke liye hain."
    ),
    "games": (
        "🎮 **Word Games**\n\n"
        "`/wordpuzzle easy|medium|hard` — Scrambled word solve karo\n"
        "`/missing easy|medium|hard` — Missing-letter puzzle\n"
        "⭐ Medium aur Hard missing-letter modes included hain.\n"
        "`/gamescore` — Game points aur coins dekho\n`/coins` — Apna coin balance dekho\n`/topcoins` — Top 10 coin leaderboard\n"
        "`/gamecancel` — Active game cancel karo\n\n"
        "Correct answer par difficulty ke points aur winner ko **300 🪙 coins** milte hain. `/topcoins` se Top 10 dekho."
    ),
}


def help_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("ℹ️ General", callback_data="help_general")],
            [InlineKeyboardButton("🎵 Music & Video", callback_data="help_music")],
            [InlineKeyboardButton("🛠 Group Management", callback_data="help_admin")],
            [InlineKeyboardButton("🎮 Word Games", callback_data="help_games")],
            [InlineKeyboardButton("👑 Owner & Sudo", callback_data="help_sudo")],
            [InlineKeyboardButton("❌ Close", callback_data="help_close")],
        ]
    )


def help_section_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="help_main")]]
    )
