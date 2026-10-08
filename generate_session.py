"""
Ye script sirf ek baar chalao — apne LOCAL computer par, Pella par nahi —
taaki assistant (userbot) account ka SESSION_STRING generate ho jaye.

Ye assistant account VC me "join" hoga taaki music stream ho sake.
Bot account khud VC join nahi kar sakta, isliye ek dusra normal Telegram
account (jo aapka apna number ho sakta hai, ya spare account) chahiye.

Chalane ka tarika:
    pip install pyrogram tgcrypto python-dotenv
    python generate_session.py

Phone number, OTP, aur (agar 2FA on hai to) password maangega.
Aakhir me jo string print hoga, use .env file ke SESSION_STRING me daal do.
"""

import os
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")

with Client("assistant_session_gen", api_id=API_ID, api_hash=API_HASH, in_memory=True) as app:
    session_string = app.export_session_string()
    print("\n\nYe raha aapka SESSION_STRING (.env me paste karo):\n")
    print(session_string)
    print("\n\nIse kisi ke saath share mat karna — ye aapke Telegram account ka pura access deta hai.")
