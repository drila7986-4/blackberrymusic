"""Entry point for hosts (like Pella) that expect a main.py specifically.

All the actual bot logic lives in bot.py - this file just launches it,
so there's only one copy of the logic to keep in sync.
"""
import asyncio

from bot import main
from keep_alive import keep_alive

if __name__ == "__main__":
    keep_alive()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
