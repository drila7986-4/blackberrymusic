# Blackberry Music — Telegram Music Bot (VC audio/video streaming + downloads + group management)

Features:
- `/play <song/link>` — group **voice chat** me audio stream karta hai (PyTgCalls)
- `/vplay <video/link>` — group **voice chat** me video (audio ke saath) stream karta hai
- `/song <song/link>` — seedha **MP3 file** bhej deta hai chat me (yt-dlp)
- Kisi audio/video message par **reply** karke `/play` ya `/vplay` bhejo — wahi media VC me chalega
- **Help menu** — `/start` ya `/help` par ❓ Help button, categorized command list ke saath
- **Group management** — kick, mute/unmute, pin/unpin, purge, warning system, admin list, per-group settings toggle

## ⚠️ Security note

Your uploaded copy of this project had a **real, live `.env` file** in it — `API_ID`, `API_HASH`,
`BOT_TOKEN`, and a full `SESSION_STRING` for the assistant userbot account. That `SESSION_STRING`
in particular gives whoever holds it full control of that Telegram account (read messages, join
voice chats, etc. — same access as a login), so it's just as sensitive as a password.

`config.py` also shipped with that same bot token hardcoded as a fallback default, which means the
secret was effectively committed to source, not just kept in `.env`. That's fixed in this delivery
(no more hardcoded fallback secrets), but the credentials themselves have already existed in a
non-.env-only location, so as a precaution you should:

1. Regenerate `API_HASH` for your api_id at https://my.telegram.org if you're unsure it's still private.
2. Revoke the current bot token via [@BotFather](https://t.me/BotFather) → `/revoke` and generate a new one.
3. Re-run `generate_session.py` for the assistant account to get a fresh `SESSION_STRING`, since the
   old one can't be "rotated" — only replaced.
4. Put the new values only in your local `.env` (never in `config.py` or any file you share/commit).
5. The `MONGO_URI` in `.env` also has a real username/password embedded (`Lucky:Lucky1976@...`) that was shared in plain text — treat it as compromised too. In MongoDB Atlas, go to **Database Access**, edit that user, and set a new password, then update `MONGO_URI` in `.env` to match.

## 1. Credentials nikalo

1. **API_ID / API_HASH** — https://my.telegram.org → API Development Tools se milega.
2. **BOT_TOKEN** — Telegram par [@BotFather](https://t.me/BotFather) se `/newbot` karke.
3. **SESSION_STRING** — ye zaroori hai VC join karne ke liye, kyunki bot account khud VC join nahi kar sakta. Iske liye ek **dusra normal Telegram account** (spare number chalega) chahiye jo "assistant" ban ke VC me baithega.

   Apne computer par (Pella par nahi):
   ```
   pip install pyrogram tgcrypto python-dotenv
   python generate_session.py
   ```
   Phone number + OTP daalo, jo string milegi wo `SESSION_STRING` me daal do.
4. **MONGO_URI** — MongoDB Atlas (ya kisi bhi MongoDB) ka connection string, jaisa `mongodb+srv://<user>:<password>@<cluster>/?appName=<name>` format me hota hai. Isi database me sudo list, gban list, group settings, aur warnings store hoti hain. `MONGO_DB_NAME` optional hai (default `blackberry_music`).

   ⚠️ Is string me username/password embedded hote hain — isse `.env` me hi rakho, kabhi kisi ke saath share ya commit mat karo. Agar ye password kabhi kisi chat/screenshot me expose ho gaya ho, Atlas se turant reset kar do.

## 2. Local test (optional but recommended)

```
pip install -r requirements.txt
cp .env.example .env
# .env file me apni values bhar do
python bot.py
```

FFmpeg system me installed hona chahiye:
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: ffmpeg.org se download karke PATH me daalo

## 3. Pella.app par deploy karna

1. Pella dashboard me naya **app/server** banao — type me "Python" ya generic app select karo.
2. Ye poora folder zip karke upload karo, ya Git repo connect karo.
3. **Environment variables** (Pella panel me) add karo — sab kuch jo `.env.example` me hai:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `SESSION_STRING`
   - `OWNER_ID`
   - `MONGO_URI`
   - `MONGO_DB_NAME` (optional, default `blackberry_music`)
   - `DOWNLOAD_DIR` (optional, default `downloads`)
   - `BOT_NAME`, `SUPPORT_CHAT`, `UPDATE_CHANNEL` (optional, branding)
4. **Start command:** `pip install -r requirements.txt && python main.py`
   (Har deploy/restart par dependencies fresh install honi chahiye — sirf
   `python main.py` use karoge to purani/missing packages (jaise TgCrypto)
   silently reh sakti hain agar Pella pehle se ek baar hi install kar chuka hai.)
5. Console me deploy ke turant baad "TgCrypto is missing!" warning check karo:
   - Agar dikhe, iska matlab upar wala start command sahi se save/apply nahi hua,
     ya `pip install` step fail ho raha hai — console me thoda upar scroll karke
     dekho ki `tgcrypto` install karte waqt koi error to nahi (missing C compiler,
     unsupported architecture jaisa Alpine/musl, etc.). Agar error dikhe to Pella
     support/Discord se pooch lo unka base image kya hai.
   - TgCrypto na hone se Pyrogram chalta to hai, par MTProto encryption bahut
     slow (pure Python) ho jaati hai — jab `/play` ke waqt CPU already yt-dlp +
     ffmpeg se busy ho, ye extra slowness event loop/connection ko choke kar
     sakti hai aur "server offline" jaisa dikh sakta hai. Isliye ye fix karna
     zaroori hai, sirf speed ke liye nahi.
6. Console me check karo ki **FFmpeg installed** hai — agar nahi hai to Pella ke
   support/Discord se pooch lo ki ffmpeg buildpack/package kaise add karein, kyunki
   ye VC streaming ke liye zaroori hai.
7. Free tier par VC streaming (`/play`) resource-heavy hai aur free containers
   ~24h me sleep/renew maangte hain — 24/7 chalana hai to paid plan (~$2-3/mo) better rahega.
   `/song` (sirf MP3 download-send) free tier par bhi theek chal jayega.
   Agar upar ke fixes ke baad bhi `/play` chalate hi server offline ho jaata hai,
   console logs me turant us waqt "OOM" / "killed" jaisa kuch dikhe to ye pakka
   resource-limit issue hai — us case me paid plan hi realistic fix hai, code me
   aur kuch optimize karne se nahi bachega.

## Bot ko group me use karna

1. Bot account ko group me **admin** banao (VC control ke liye).
2. Assistant account (jiska SESSION_STRING banaya) ko bhi group me **normal member** ki tarah add karo.
3. Group ki voice chat pehle se **on/start** honi chahiye — bot khud VC start nahi karta, sirf join karke stream karta hai.
4. Ab `/play <song name>` bhejo group me.

## Commands

| Command | Kaam |
|---|---|
| `/start` | Bot ka intro (private chat me special welcome, group me short intro) — ❓ Help button ke saath |
| `/help` | Categorized help menu (Music & Video / Group Management / Owner & Sudo) |
| `/play <song/link>` | VC me audio stream/queue karo — reply karke bhi chala sakte ho |
| `/vplay <video/link>` | VC me video (audio ke saath) stream/queue karo — reply karke bhi chala sakte ho |
| `/pause` | Playback pause |
| `/resume` | Playback resume |
| `/skip` | Agla item queue se |
| `/stop` | Music/video band, queue clear, VC se exit |
| `/queue` | Current queue dekho (🎵 audio / 🎥 video icon ke saath) |
| `/song <song/link>` | MP3 file directly bhejo (VC ki zarurat nahi) |
| `/kick` | *(Group admin/Sudo)* User ko group se kick karo (ban nahi, wapas join kar sakta hai) |
| `/mute` / `/unmute` | *(Group admin/Sudo)* User ke messages restrict/unrestrict karo |
| `/pin` / `/unpin` | *(Group admin/Sudo)* Reply kiye gaye message ko pin/unpin karo |
| `/purge` | *(Group admin/Sudo)* Reply se lekar is message tak sab delete karo |
| `/warn` | *(Group admin/Sudo)* User ko warn karo — reason ke saath (3 warnings = auto-ban) |
| `/warnings` | Kisi user (ya khud) ke warnings dekho |
| `/resetwarn` | *(Group admin/Sudo)* User ke warnings reset karo |
| `/admins` | Group ke saare admins list karo |
| `/settings` | *(Group admin/Sudo)* Welcome message & clean-service-messages toggle karo (inline buttons) |
| `/ban` | *(Group admin/Sudo)* User ko is group se ban karo — reply/tag/@username/user_id se target karo |
| `/unban` | *(Group admin/Sudo)* User ko is group me unban karo |
| `/addsudo <user_id>` | *(Owner only)* Naya sudo user banao |
| `/delsudo <user_id>` | *(Owner only)* Sudo user hatao |
| `/sudolist` | *(Owner/Sudo)* Sudo users ki list dekho |
| `/selfadmin` | *(Owner/Sudo)* Bot khud ko group me admin banane ki koshish karta hai |
| `/selfpromote` or `/promoteme` | *(Owner/Sudo)* Khud ko (jo command bheje) is group me admin banao |
| `/gban [reason]` | *(Owner/Sudo)* User ko globally ban karo — reply/tag/@username/user_id se target karo |
| `/ungban` | *(Owner/Sudo)* User ko global ban se hatao |
| `/gbanlist` | *(Owner/Sudo)* Sab globally banned users dekho |

> Sab targeted commands (`ban`, `unban`, `kick`, `mute`, `unmute`, `warn`, `warnings`, `resetwarn`, `gban`, `ungban`) 4 tarike se target user le sakte hain: **reply**, **tag**, **@username**, ya **user_id**.

## Self Admin Power

- Jab bot kisi naye group me **add** hota hai, wo turant khud ko **admin** banane ki koshish karta hai — assistant account ke through (`assistant.promote_chat_member`).
- Ye tabhi kaam karega jab **assistant account** us group me pehle se admin ho aur uske paas **"Add New Admins"** permission ho. Agar nahi hai, to bot ek message bhejega ki use manually admin banao.
- Agar auto-promote miss ho jaye (jaise bot pehle se group me tha, feature baad me add hui), owner/sudo `/selfadmin` command se dobara try kara sakte hain.
- **Owner aur Sudo users** ko har group me "admin power" milti hai — chahe Telegram me unhe actually admin banaya gaya ho ya nahi. Isliye `/pause`, `/resume`, `/skip`, `/stop` jaise control commands owner/sudo ke liye hamesha kaam karenge; baaki members ke liye ye sirf tab kaam karenge jab wo us group ke real Telegram admin hon.
- `/selfpromote` (ya `/promoteme`) se owner/sudo **khud ko** us group me actual Telegram admin bhi bana sakte hain — bot ya assistant, jiske paas bhi "Add New Admins" permission ho, wo use karke promote karega.

## Owner, Sudo & Branding

- **Bot name** startup par khud-b-khud Telegram Bot API (`setMyName`) se set ho jata hai — `.env` me `BOT_NAME` change karke naam badal sakte ho.
- **Owner ID** (`OWNER_ID`) ko hardcoded/env se set kiya hai — is user ko `/addsudo`, `/delsudo`, `/sudolist` ka access hai.
- **Sudo users** MongoDB me persist hote hain (`.env` ka `MONGO_URI`) — bot restart hone par bhi yaad rehte hain.
- **VIP welcome:** Jab owner ya koi sudo user kisi aise group me join karta hai jaha bot pehle se maujood hai, bot automatically ek special welcome message bhejta hai — Owner, Support Chat aur Update Channel ke inline buttons ke saath.
- `/start` command bhi hamesha ye teen buttons dikhata hai — private chat me ek special, zyada detailed welcome message aata hai (jisme ek extra "Add me to your group" button bhi hota hai), group me short intro.

Ye teeno cheezein bina kuch aur karo already set hain: Support Chat, Update Channel, Owner button — sab `.env` ya `config.py` se aa rahe hain, chahen to wahi se change kar sakte ho.

## 24x7 Keep-Alive (Flask)

Bot ke saath ek chhota **Flask web server** bhi chalta hai (`keep_alive.py`), jo
`/` route par "Bot zinda hai" reply karta hai. Ye do kaam ke liye hai:

1. Agar Pella tumhare app ko "web service" expect karta hai (port par listen karna), to ye server wo zarurat pura kar deta hai.
2. Agar tum koi free **uptime pinger** (jaise UptimeRobot, cron-job.org) is URL par har 5 minute me ping karwao, to free tier par bot sone/sleep hone se bach sakta hai.

Setup:
- Server `PORT` env variable use karta hai (default `8080`) — Pella jo bhi port assign kare wo automatically use ho jayega.
- Bot start hote hi ye server bhi khud-b-khud start ho jata hai, alag se kuch karne ki zarurat nahi.
- Chaho to apna Pella app ka public URL kisi uptime pinger me daal ke har 5 min ping set kar do, taaki free tier par bhi bot zyada der tak jaga rahe.

## Ban & Global Ban (Gban)

Kisi bhi user ko target karne ke **4 tarike** hain, `/ban`, `/unban`, `/gban`, `/ungban` — sab me kaam karte hain:
1. Us user ke kisi **message par reply** karke command bhejo
2. Use **tag** karo (Telegram me kisi ko mention karna)
3. Uska **@username** likho
4. Uska **user_id** likho

**`/ban` / `/unban`** — sirf us group tak seemit hai jaha command chala; **group admin ya sudo/owner** use kar sakte hain.

**`/gban` / `/ungban` / `/gbanlist`** — global level par kaam karta hai, sirf **Owner/Sudo** use kar sakte hain:
- `/gban` us user ko **bot ke har group** se turant ban kar deta hai, aur ek permanent list MongoDB me daal deta hai.
- Jab bhi gbanned user **naya message bhejega** kisi bhi group me jaha bot hai, bot use turant delete karke us group se bhi ban kar dega.
- Agar gbanned user kisi **naye group me join** karega jaha bot pehle se hai, wo turant kick ho jayega.
- `/ungban` global ban hatata hai, aur bot ke saare groups me se unban bhi karta hai.
- `/gbanlist` sab globally banned users aur unke reasons dikhata hai.
- Owner/sudo ko khud ban/gban nahi kiya ja sakta.
- In sab commands ke kaam karne ke liye bot ko us group me **admin** hona chahiye (ban karne ki permission ke saath) — jo already "Self Admin Power" feature se handle ho jata hai.

## User & Admin Caching (bounded, not bulk tracking)

This bot does **not** passively track every member of every group. Three specific, scoped
things are cached instead:

1. **Command users** — anyone who runs a bot command has their name/username upserted into
   MongoDB (`known_users`), so the bot remembers who's interacted with it. People who never
   use a command are never touched by this.
2. **Moderation/sudo targets** — when someone is warned, banned, kicked, muted, or added as
   sudo, that target's info is cached too (tied to a real, explicit bot action).
3. **Group admin lists** — every 10 minutes, `group_admin_cache.py` refreshes just the
   **admin list** (not full member lists) for each group the bot is in, so `/groupadmins`
   can show a quick cross-group overview without hitting the Telegram API on demand every
   time. Admin lists are already public info any group member can see via `/admins`.

New commands:
- `/whois <reply/tag/@username/user_id>` — on-demand lookup of one user's current info
  (name, ID, sudo status, gban status, last cached interaction). Group admins and sudo can
  use this in groups; anyone can check their own info in a private chat.
- `/groupadmins` (or `/allgroupadmins`) — sudo/owner-only, shows the cached admin list per
  group along with when it was last refreshed.

## Broadcast

`/broadcast <text>` (or reply to any message — text, photo, video, document) sends that
content to every chat the **bot account** has a dialog with, and pins it automatically in
every group it lands in.

- **Groups** — sent and pinned (pinning silently no-ops if the bot doesn't have pin
  permission in that particular group).
- **Personal (DM) chats** — sent only to users who have an existing private chat with the
  bot. This isn't a policy choice you can turn off — it's how Telegram's Bot API itself
  works: a bot can never initiate a DM with someone who hasn't started a conversation with
  it first. So `/broadcast` can only ever reach people who already opted in by messaging
  the bot, never a cold list of arbitrary users.
- Sudo/owner only. It's irreversible once sent (no "undo broadcast"), so double-check the
  message/reply before running it. A FloodWait from Telegram on any single chat is waited
  out and retried once; a failure on one chat doesn't stop the rest of the broadcast. You
  get a summary (`sent` / `pinned` / `failed` for groups and DMs) when it finishes.

## Notes

- Ye code **PyTgCalls v2.x** API use karta hai. Agar library update hone par kuch
  method names badal jayein, to error message dekh ke `bot.py` me us function call
  ko adjust karna padega.
- Downloaded files `downloads/` folder me temporarily banti hain aur use ke baad
  khud delete ho jaati hain.
