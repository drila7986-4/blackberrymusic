from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, MONGO_DB_NAME

_client = AsyncIOMotorClient(MONGO_URI)
db = _client[MONGO_DB_NAME]

# Collections used across the bot's storage modules
sudo_col = db["sudo_users"]
gban_col = db["gban_users"]
settings_col = db["chat_settings"]
warnings_col = db["warnings"]
playlist_col = db["playlists"]

coins_col = db["game_coins"]

# Users who explicitly started the bot in private chat (required for group games)
game_users_col = db["game_users"]
