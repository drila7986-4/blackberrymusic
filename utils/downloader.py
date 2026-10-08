import os
import yt_dlp
from config import DOWNLOAD_DIR

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Free/low-tier hosts (like Pella's free plan) have limited RAM/disk/CPU.
# A long or high-res video can eat all of it and take the whole bot down.
# These caps keep /play and /vplay from downloading anything that large.
MAX_DURATION_SECONDS = int(os.environ.get("MAX_MEDIA_DURATION_SECONDS", "1200"))  # 20 min


def _check_duration(info: dict):
    duration = info.get("duration")
    if duration and duration > MAX_DURATION_SECONDS:
        raise ValueError(
            f"Ye media {duration // 60} minute ka hai, jo {MAX_DURATION_SECONDS // 60} minute "
            "ki limit se zyada hai (server resources bachane ke liye). Chhota gaana/video try karo."
        )


def search(query: str):
    """Search YouTube and return basic info without downloading."""
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]
        return {
            "title": info.get("title"),
            "url": info.get("webpage_url"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
        }


def download_mp3(query_or_url: str):
    """Download and convert to mp3 - used for /song (direct file send)."""
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query_or_url, download=True)
        if "entries" in info:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        mp3_path = base + ".mp3"
        return mp3_path, info.get("title")


def download_for_vc(query_or_url: str):
    """Download raw best-audio file - used for /play (voice chat streaming).
    PyTgCalls/ffmpeg handles transcoding internally, so no mp3 conversion needed here."""
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "outtmpl": f"{DOWNLOAD_DIR}/vc_%(id)s.%(ext)s",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query_or_url, download=False)
        if "entries" in info:
            info = info["entries"][0]
        _check_duration(info)
        info = ydl.extract_info(query_or_url, download=True)
        if "entries" in info:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        return filename, info.get("title"), info.get("duration"), info.get("webpage_url")


def download_video_for_vc(query_or_url: str):
    """Download video+audio (muxed to mp4) - used for /vplay (voice chat video streaming).
    Works with a search query or a direct YouTube (or other yt-dlp supported) URL."""
    opts = {
        # Capped at 480p to match the VideoQuality.SD_480p used for playback anyway -
        # downloading a bigger file than what actually gets streamed just wastes
        # disk/RAM/bandwidth on the host for nothing.
        "format": "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "outtmpl": f"{DOWNLOAD_DIR}/vplay_%(id)s.%(ext)s",
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query_or_url, download=False)
        if "entries" in info:
            info = info["entries"][0]
        _check_duration(info)
        info = ydl.extract_info(query_or_url, download=True)
        if "entries" in info:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        mp4_path = base + ".mp4"
        if not os.path.exists(mp4_path):
            mp4_path = filename
        return mp4_path, info.get("title"), info.get("duration"), info.get("webpage_url")
