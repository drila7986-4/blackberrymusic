import random
import re
import time
from collections import defaultdict

WORDS = {
    "easy": ["apple", "chair", "house", "water", "music", "tiger", "green", "happy", "phone", "river"],
    "medium": ["journey", "library", "monster", "picture", "rainbow", "diamond", "morning", "holiday", "teacher", "station"],
    "hard": ["adventure", "beautiful", "knowledge", "important", "impossible", "mysterious", "experience", "wonderful", "technology", "celebrate"],
}

DIFFICULTY = {"easy": 5, "medium": 10, "hard": 15}
GAME_TIMEOUT = 90
ACTIVE_GAMES = {}
SCORES = defaultdict(int)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def _scramble(word: str) -> str:
    chars = list(word)
    for _ in range(10):
        random.shuffle(chars)
        candidate = "".join(chars)
        if candidate != word:
            return candidate
    return "".join(chars)


def _missing(word: str, difficulty: str):
    if difficulty == "easy":
        count = 1
    elif difficulty == "medium":
        count = min(2, max(1, len(word) // 4))
    else:
        count = min(4, max(3, len(word) // 3))

    indexes = sorted(random.sample(range(len(word)), min(count, len(word) - 1)))
    shown = list(word)
    for i in indexes:
        shown[i] = "_"
    return " ".join(shown), len(indexes)


def new_puzzle(chat_id: int, game_type: str, difficulty: str = "medium"):
    difficulty = difficulty.lower()
    if difficulty not in WORDS:
        difficulty = "medium"
    word = random.choice(WORDS[difficulty])
    if game_type == "word":
        puzzle = _scramble(word)
        prompt = (
            f"🧩 **WORD PUZZLE — {difficulty.upper()}**\n\n"
            f"Unscramble this word:\n\n🔤 `{puzzle}`\n\n"
            f"⏱️ Time: {GAME_TIMEOUT}s\n"
            f"🏆 Points: +{DIFFICULTY[difficulty]}"
        )
    else:
        puzzle, missing_count = _missing(word, difficulty)
        prompt = (
            f"🔤 **MISSING LETTER — {difficulty.upper()}**\n\n"
            f"Complete the word:\n\n🧩 `{puzzle}`\n\n"
            f"💡 Missing letters: {missing_count}\n"
            f"⏱️ Time: {GAME_TIMEOUT}s\n"
            f"🏆 Points: +{DIFFICULTY[difficulty]}"
        )

    ACTIVE_GAMES[chat_id] = {
        "type": game_type,
        "difficulty": difficulty,
        "answer": word,
        "started": time.monotonic(),
        "points": DIFFICULTY[difficulty],
    }
    return prompt


def check_answer(chat_id: int, answer: str):
    game = ACTIVE_GAMES.get(chat_id)
    if not game:
        return None
    if time.monotonic() - game["started"] > GAME_TIMEOUT:
        ACTIVE_GAMES.pop(chat_id, None)
        return {"status": "timeout", "answer": game["answer"]}

    if normalize(answer) == normalize(game["answer"]):
        points = game["points"]
        ACTIVE_GAMES.pop(chat_id, None)
        return {"status": "correct", "answer": game["answer"], "points": points}
    return {"status": "wrong"}


def cancel_game(chat_id: int):
    return ACTIVE_GAMES.pop(chat_id, None)


def score(user_id: int) -> int:
    return SCORES[user_id]


def add_score(user_id: int, points: int) -> int:
    SCORES[user_id] += points
    return SCORES[user_id]
