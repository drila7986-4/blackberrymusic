"""Tracks the live 'Now Playing' card (progress bar + controls) per chat.

Playback position isn't queryable from PyTgCalls directly, so elapsed time is
estimated from wall-clock time since the stream started, minus any time spent
paused. That's the same approach most Telegram music bots use.
"""

import time

# chat_id -> {
#   "title", "kind", "duration", "requested_by", "url",
#   "start_ts", "paused", "paused_at", "paused_total",
#   "msg" (Message being edited), "task" (asyncio.Task updating it),
# }
now_playing = {}


def format_time(seconds) -> str:
    seconds = int(seconds or 0)
    if seconds < 0:
        seconds = 0
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def render_progress_bar(elapsed: float, total: float, length: int = 10) -> str:
    if not total or total <= 0:
        return "▬" * length
    ratio = min(max(elapsed / total, 0), 1)
    pos = int(ratio * (length - 1))
    return "".join("●" if i == pos else "▬" for i in range(length))


def get_elapsed(chat_id) -> float:
    state = now_playing.get(chat_id)
    if not state:
        return 0
    if state["paused"]:
        return max(state["paused_at"] - state["start_ts"] - state["paused_total"], 0)
    return max(time.time() - state["start_ts"] - state["paused_total"], 0)


def new_state(title, kind, duration, requested_by, url) -> dict:
    return {
        "title": title,
        "kind": kind,
        "duration": duration or 0,
        "requested_by": requested_by,
        "url": url,
        "start_ts": time.time(),
        "paused": False,
        "paused_at": None,
        "paused_total": 0.0,
        "msg": None,
        "task": None,
    }


def reset_timer(state: dict):
    """Used on replay - restarts elapsed-time tracking from zero."""
    state["start_ts"] = time.time()
    state["paused"] = False
    state["paused_at"] = None
    state["paused_total"] = 0.0


def clear_state(chat_id):
    state = now_playing.pop(chat_id, None)
    if state and state.get("task"):
        state["task"].cancel()
    return state
