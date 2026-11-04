import os
import sys
import subprocess
from pathlib import Path

def default_cache_dir():
    home = Path.home()
    if sys.platform == "darwin":
        candidates = [home / "Library/Containers/com.netease.163music/Data/Library/Caches/online_play_cache", home / "Library/Containers/com.netease.163music/Data/Caches/online_play_cache", home / "Library/Caches/com.netease.163music/online_play_cache"]
        return next((p for p in candidates if p.is_dir()), candidates[0])
    return home / "AppData/Local/NetEase/CloudMusic/Cache/Cache"

def tool_paths(bundle):
    if sys.platform == "darwin":
        ffmpeg = bundle / "tools/ffmpeg/bin/ffmpeg"
        return ffmpeg, bundle / "tools/encoder/ffmpeg", ffmpeg.with_name("ffprobe")
    return bundle / "tools/mpv/Yaoplayer.com", bundle / "tools/ffmpeg/ffmpeg.exe", bundle / "tools/ffmpeg/ffprobe.exe"

def open_path(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
