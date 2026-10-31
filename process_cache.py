#!/usr/bin/env python3
"""Convert NetEase Cloud Music .uc cache files into an AURAL-ready collection.

This script is local-first: it never uploads files to AURAL. It chooses the
largest cache file for each numeric song ID, decodes .uc with XOR 0xA3, asks a
public metadata endpoint for available tags/cover/lyrics, converts to 128 kbps
stereo MP3 with the AV3A-capable mpv-Yaozhi core, and writes a review manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = Path(os.environ.get(
    "NETEASE_CACHE_DIR",
    Path.home() / "AppData" / "Local" / "NetEase" / "CloudMusic" / "Cache" / "Cache",
))
DEFAULT_OUTPUT = Path(os.environ.get(
    "NETEASE_OUTPUT_DIR",
    Path.home() / "Documents" / "声匣转换结果",
))
DEFAULT_MPV = Path(os.environ.get(
    "MPV_CORE_DIR",
    PROJECT_DIR / "vendor-tools" / "mpv" / "Yaoplayer.com",
))
DEFAULT_FFMPEG = Path(os.environ.get(
    "FFMPEG_BIN_DIR",
    PROJECT_DIR / "vendor-tools" / "ffmpeg",
)) / "ffmpeg.exe"
DEFAULT_FFPROBE = DEFAULT_FFMPEG.with_name("ffprobe.exe")
METADATA_ENDPOINT = "https://api.injahow.cn/meting/"
XOR_TABLE = bytes.maketrans(bytes(range(256)), bytes((b ^ 0xA3) for b in range(256)))


def request(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Referer": "https://music.163.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def get_metadata(song_id: str, cache_dir: Path) -> dict:
    cache_file = cache_dir / f"{song_id}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    query = urllib.parse.urlencode({"server": "netease", "type": "song", "id": song_id})
    try:
        raw = json.loads(request(f"{METADATA_ENDPOINT}?{query}").decode("utf-8-sig"))
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError):
        raw = {}
    cache_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(0.35)
    return raw


def get_album_details(song_id: str) -> tuple[str, str]:
    """Fetch album name and ID from NetEase song detail when Meting omits them."""
    encoded_id = urllib.parse.quote(song_id, safe="")
    ids = urllib.parse.quote(f"[{song_id}]", safe="")
    url = f"https://music.163.com/api/song/detail/?id={encoded_id}&ids={ids}"
    try:
        payload = json.loads(request(url, timeout=15).decode("utf-8-sig"))
        songs = payload.get("songs", []) if isinstance(payload, dict) else []
        song = songs[0] if songs and isinstance(songs[0], dict) else {}
        album = song.get("al") or song.get("album") or {}
        if isinstance(album, dict):
            return text_value(album.get("name")), text_value(album.get("id"))
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError, AttributeError):
        pass
    return "", ""


def album_values(meta: dict) -> tuple[str, str]:
    """Read common album shapes returned by music metadata providers."""
    album = meta.get("album") or meta.get("al") or {}
    if isinstance(album, dict):
        return text_value(album.get("name")), text_value(album.get("id"))
    return text_value(album), text_value(meta.get("album_id"))


def text_value(value) -> str:
    if isinstance(value, list):
        return " / ".join(str(x) for x in value if x)
    return str(value or "").strip()


def safe_name(value: str, fallback: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return (value or fallback)[:150]


def run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def decode_uc(source: Path, decoded: Path) -> None:
    with source.open("rb") as reader, decoded.open("wb") as writer:
        while True:
            block = reader.read(4 * 1024 * 1024)
            if not block:
                break
            writer.write(block.translate(XOR_TABLE))


def fetch_optional(url: str, destination: Path) -> bool:
    if not url:
        return False
    try:
        destination.write_bytes(request(url, timeout=30))
        return destination.stat().st_size > 0
    except (OSError, urllib.error.URLError):
        destination.unlink(missing_ok=True)
        return False


def fetch_cover(url: str, destination: Path, ffprobe: Path) -> bool:
    """Ask NetEase's cover endpoint/CDN for a larger image, then fall back to its original URL."""
    if not url:
        return False
    candidates = []
    try:
        resolved = url
        if urllib.parse.urlsplit(url).netloc.lower() == "api.injahow.cn":
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            req = urllib.request.Request(url, headers={"User-Agent": "AuralCachePrep/1.0"})
            try:
                opener.open(req, timeout=15)
            except urllib.error.HTTPError as response:
                if response.headers.get("Location"):
                    resolved = urllib.parse.urljoin(url, response.headers["Location"])
        for candidate in (resolved, url):
            parsed = urllib.parse.urlsplit(candidate)
            if parsed.netloc.lower().endswith("music.126.net"):
                query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
                query["param"] = "1000y1000"
                candidates.append(urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query))))
        candidates.append(url)
    except ValueError:
        candidates = [url]
    for candidate in dict.fromkeys(candidates):
        try:
            data = request(candidate, timeout=30)
            if data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")) and len(data) > 2048:
                destination.write_bytes(data)
                probe = run([str(ffprobe), "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height", "-of", "json", str(destination)],
                            destination.parent, 20)
                dims = json.loads(probe.stdout).get("streams", []) if probe.returncode == 0 else []
                if dims and int(dims[0].get("width", 0)) >= 500 and int(dims[0].get("height", 0)) >= 500:
                    return True
        except (OSError, ValueError, urllib.error.URLError):
            continue
        destination.unlink(missing_ok=True)
    destination.unlink(missing_ok=True)
    return False


def prepare_upload_audio(source: Path, destination: Path) -> None:
    """Expose the checked audio in ready_to_upload without duplicating bytes when possible."""
    if destination.exists():
        return
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def probe_audio(ffprobe: Path, path: Path) -> dict:
    result = run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration,format_name",
         "-show_entries", "stream=codec_name,codec_type,channels,sample_rate",
         "-of", "json", str(path)], path.parent, 30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe could not read output")
    info = json.loads(result.stdout)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not audio:
        raise RuntimeError("No audio stream detected")
    return {"format": info.get("format", {}).get("format_name", ""),
            "duration_seconds": round(float(info.get("format", {}).get("duration", 0))),
            "source_codec": audio.get("codec_name", "unknown"),
            "source_channels": audio.get("channels", 0),
            "sample_rate": audio.get("sample_rate", "")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=r"NetEase Cache\Cache directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="New collection folder")
    parser.add_argument("--mpv", type=Path, default=DEFAULT_MPV, help="AV3A-capable Yaoplayer.com/mpv core")
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--ffprobe", type=Path, default=DEFAULT_FFPROBE)
    parser.add_argument("--limit", type=int, default=0, help="Process only first N unique IDs (trial run)")
    parser.add_argument("--keep-decoded", action="store_true", help="Keep temporary XOR-decoded source files")
    parser.add_argument("--force", action="store_true", help="Rebuild existing MP3s")
    args = parser.parse_args()

    for label, path in (("source directory", args.source), ("mpv core", args.mpv),
                        ("ffmpeg", args.ffmpeg), ("ffprobe", args.ffprobe)):
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2
    files = sorted(args.source.glob("*.uc"))
    if not files:
        print(f"ERROR: no .uc files in {args.source}", file=sys.stderr)
        return 2

    # Multiple cache files may represent different quality/cache variants of one ID.
    by_id: dict[str, list[Path]] = {}
    for path in files:
        song_id = path.name.split("-", 1)[0]
        if song_id.isdigit():
            by_id.setdefault(song_id, []).append(path)
    selected = [(song_id, max(group, key=lambda p: p.stat().st_size), group)
                for song_id, group in sorted(by_id.items(), key=lambda item: int(item[0]))]
    if args.limit:
        selected = selected[:args.limit]

    output = args.output
    audio_dir, cover_dir, lyrics_dir = output / "audio", output / "covers", output / "lyrics"
    ready_dir, temp_dir, metadata_dir = output / "ready_to_upload", output / "work" / "decoded", output / "work" / "metadata"
    for directory in (audio_dir, cover_dir, lyrics_dir, ready_dir, temp_dir, metadata_dir):
        directory.mkdir(parents=True, exist_ok=True)

    records = []
    for index, (song_id, cache_file, variants) in enumerate(selected, 1):
        meta = get_metadata(song_id, metadata_dir)
        title = text_value(meta.get("name")) or f"Unknown title {song_id}"
        artist = text_value(meta.get("artist")) or "Unknown artist"
        album, album_id = album_values(meta)
        if not album:
            album, album_id = get_album_details(song_id)
            if album:
                meta["album"] = album
                if album_id:
                    meta["album_id"] = album_id
                (metadata_dir / f"{song_id}.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        stem = safe_name(f"{artist} - {title}", song_id)
        mp3 = audio_dir / f"{stem}.mp3"
        ready_mp3 = ready_dir / mp3.name
        decoded = temp_dir / f"{song_id}.audio"
        record = {"song_id": song_id, "title": title, "artist": artist, "album": album,
                  "album_id": album_id,
                  "cache_file": cache_file.name, "cache_variants": [p.name for p in variants],
                  "mp3_path": str(mp3), "ready_to_upload_path": str(ready_mp3),
                  "status": "pending", "error": ""}
        try:
            if args.force or not mp3.exists() or mp3.stat().st_size < 4096:
                decode_uc(cache_file, decoded)
                source_info = probe_audio(args.ffprobe, decoded)
                temp_mp3 = temp_dir / f"{song_id}.mp3"
                converted = run(
                    [str(args.mpv), "--no-config", "--no-video", f"--o={temp_mp3}", "--of=mp3",
                     "--oac=libmp3lame", "--oacopts=b=128000", "--audio-channels=stereo",
                     "--msg-level=all=warn", str(decoded)], args.mpv.parent, 900,
                )
                if converted.returncode or not temp_mp3.exists() or temp_mp3.stat().st_size < 4096:
                    raise RuntimeError(converted.stderr.strip()[-1200:] or "mpv conversion failed")

                cover_path = cover_dir / f"{song_id}.jpg"
                got_cover = fetch_cover(text_value(meta.get("pic")), cover_path, args.ffprobe)
                tagged = temp_dir / f"{song_id}-tagged.mp3"
                cmd = [str(args.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(temp_mp3)]
                if got_cover:
                    cmd += ["-i", str(cover_path), "-map", "0:a", "-map", "1:v", "-c:v", "mjpeg",
                            "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
                else:
                    cmd += ["-map", "0:a"]
                cmd += ["-c:a", "copy", "-id3v2_version", "3", "-metadata", f"title={title}",
                        "-metadata", f"artist={artist}", "-metadata", f"album={album}", str(tagged)]
                tagged_result = run(cmd, args.ffmpeg.parent, 120)
                if tagged_result.returncode or not tagged.exists():
                    raise RuntimeError(tagged_result.stderr.strip()[-1200:] or "ID3 tagging failed")
                tagged.replace(mp3)
                temp_mp3.unlink(missing_ok=True)
                if not args.keep_decoded:
                    decoded.unlink(missing_ok=True)
                record.update(source_info)

            verified = probe_audio(args.ffprobe, mp3)
            prepare_upload_audio(mp3, ready_mp3)
            record.update({"status": "ready", "output_duration_seconds": verified["duration_seconds"],
                           "output_format": verified["format"], "output_codec": "mp3",
                           "output_bytes": mp3.stat().st_size})
            lrc_url = text_value(meta.get("lrc"))
            if lrc_url:
                lrc = lyrics_dir / f"{stem}.lrc"
                if fetch_optional(lrc_url, lrc):
                    shutil.copy2(lrc, ready_dir / f"{stem}.lrc")
                    record["lyrics_path"] = str(lrc)
            if meta.get("pic"):
                record["cover_path"] = str(cover_dir / f"{song_id}.jpg")
        except Exception as exc:  # retain per-track failures and continue the batch
            record["status"] = "failed"
            record["error"] = str(exc)
        records.append(record)
        print(f"[{index}/{len(selected)}] {record['status']}: {artist} - {title}", flush=True)
        (output / "catalog.json").write_text(json.dumps({"source": str(args.source), "tracks": records},
                                                          ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {"source_files": len(files), "unique_song_ids": len(by_id), "processed_ids": len(records),
               "duplicate_cache_files": len(files) - len(by_id),
               "ready": sum(r["status"] == "ready" for r in records),
               "failed": sum(r["status"] == "failed" for r in records),
               "output": str(output), "uploaded": False}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
