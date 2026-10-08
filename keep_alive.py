import os
from threading import Thread

from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot zinda hai aur chal raha hai! 🎶"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    """Ek chhota web server background thread me chalata hai.
    Isse Pella (ya koi bhi host jo 'web service' expect karta hai / uptime
    pinger use karta hai) bot ko 24x7 zinda rakh sakta hai."""
    t = Thread(target=run, daemon=True)
    t.start()
