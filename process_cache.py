#!/usr/bin/env python3
"""Convert NetEase Cloud Music .uc cache files into an AURAL-ready collection.

This script is local-first: it never uploads files to AURAL. It chooses the
largest cache file for each numeric song ID, decodes .uc with XOR 0xA3, asks a
public metadata endpoint for available tags/cover/lyrics, converts to high-quality stereo MP3 or FLAC with the AV3A-capable mpv-Yaozhi core, and writes a review manifest.
"""

from __future__ import annotations

from cache_quality import resolve_cache_quality
from runtime_support import default_cache_dir

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
    default_cache_dir(),
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
pause_checkpoint = lambda: None


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
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def probe_audio(ffprobe: Path, path: Path) -> dict:
    result = run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration,format_name",
         "-show_entries", "format=bit_rate",
         "-show_entries", "stream=codec_name,codec_type,channels,sample_rate,bit_rate,codec_tag_string,bits_per_sample,bits_per_raw_sample,sample_fmt",
         "-of", "json", str(path)], path.parent, 30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe could not read output")
    info = json.loads(result.stdout)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not audio:
        raise RuntimeError("No audio stream detected")
    bit_rate = audio.get("bit_rate") or info.get("format", {}).get("bit_rate", "")
    bits = audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or ""
    return {"format": info.get("format", {}).get("format_name", ""),
            "duration_seconds": round(float(info.get("format", {}).get("duration", 0))),
            "source_codec": audio.get("codec_name") or audio.get("codec_tag_string", "unknown"),
            "source_channels": audio.get("channels", 0),
            "sample_rate": audio.get("sample_rate", ""),
            "bit_rate": int(bit_rate) if str(bit_rate).isdigit() else 0,
            "bits_per_sample": int(bits) if str(bits).isdigit() else 0,
            "sample_format": audio.get("sample_fmt", "")}


def classify_netease_quality(info: dict) -> tuple[str, str]:
    """Estimate the NetEase tier from measurable source properties, never output encoding."""
    codec = str(info.get("source_codec", "")).lower()
    rate = int(info.get("sample_rate") or 0)
    depth = int(info.get("bits_per_sample") or 0)
    bitrate = int(info.get("bit_rate") or 0)
    channels = int(info.get("source_channels") or 0)
    lossless = codec in {"flac", "alac", "ape", "wavpack", "tta", "truehd", "pcm_s16le",
                         "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_f64le"}
    if codec == "av3a":
        return "AV3A 空间音频", f"检测到 av3a 编码，{channels} 声道；原缓存未提供网易云具体音效名称"
    if lossless and rate and depth:
        if rate <= 48000 and depth <= 16:
            return "无损 SQ", "源规格符合最高 48kHz/16bit；按可测参数推定"
        if rate <= 96000 and depth <= 24:
            return "高清臻音", "源规格符合最高 96kHz/24bit；仅按可测参数推定"
        if rate <= 192000 and depth <= 24:
            return "超清母带", "源规格符合最高 192kHz/24bit；仅按可测参数推定"
        return "无损（高规格）", "检测到无损编码；不据此推定空间音频类别"
    if channels >= 6:
        return "多声道源（空间类别未确认）", f"源为 {channels} 声道；不能单凭声道数确认网易云空间音频类别"
    if bitrate and bitrate <= 192000:
        return "标准", f"源码率约 {bitrate // 1000}kbps"
    if bitrate >= 256000:
        return "极高 HQ", f"源码率约 {bitrate // 1000}kbps"
    return "品质未知", "缓存未提供足够的源码率/位深信息，避免按导出格式误标"


def source_extension(info: dict) -> str:
    """Keep the decoded cache container and codec unchanged in source mode."""
    fmt = str(info.get("format", "")).lower()
    codec = str(info.get("source_codec", "")).lower()
    if "flac" in fmt or codec == "flac":
        return ".flac"
    if any(name in fmt for name in ("mp4", "mov", "m4a", "3gp")):
        return ".m4a"
    codec_extensions = {"mp3": ".mp3", "aac": ".aac", "opus": ".opus",
                        "vorbis": ".ogg", "alac": ".m4a", "ape": ".ape",
                        "wavpack": ".wv", "tta": ".tta"}
    if codec in codec_extensions:
        return codec_extensions[codec]
    if "wav" in fmt or codec.startswith("pcm_"):
        return ".wav"
    return ".audio"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=r"NetEase Cache\Cache directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="New collection folder")
    parser.add_argument("--mpv", type=Path, default=DEFAULT_MPV, help="AV3A-capable Yaoplayer.com/mpv core")
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--ffprobe", type=Path, default=DEFAULT_FFPROBE)
    parser.add_argument("--limit", type=int, default=0, help="Process only first N unique IDs (trial run)")
    parser.add_argument("--keep-decoded", action="store_true", help="Keep temporary XOR-decoded source files")
    parser.add_argument("--force", action="store_true", help="Rebuild existing output files")
    parser.add_argument("--format", choices=("mp3", "flac", "source"), default="mp3",
                        help="MP3 320 kbps, FLAC, or preserve the decoded cache source")
    args = parser.parse_args()
    for key in ("source", "output", "mpv", "ffmpeg", "ffprobe"):
        setattr(args, key, getattr(args, key).expanduser().resolve())

    required_tools = [("ffprobe", args.ffprobe)]
    if args.format != "source":
        required_tools.extend([("mpv core", args.mpv), ("ffmpeg", args.ffmpeg)])
    for label, path in [("source directory", args.source), *required_tools]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2
    files = sorted([*args.source.glob("*.uc"), *args.source.glob("*.uc!")])
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
        pause_checkpoint()
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
        decoded = temp_dir / f"{song_id}.audio"
        try:
            decode_uc(cache_file, decoded)
            source_info = probe_audio(args.ffprobe, decoded)
            quality_label, quality_reason = classify_netease_quality(source_info)
        except Exception as exc:
            source_info = {"source_codec": "unknown", "source_channels": 0,
                           "sample_rate": "", "bit_rate": 0, "bits_per_sample": 0}
            quality_label, quality_reason = "品质未知", f"无法读取缓存音频源参数：{exc}"
        measured_quality = quality_label
        quality_evidence = resolve_cache_quality(cache_file)
        quality_label = quality_evidence["quality_label"]
        quality_reason = quality_evidence["quality_basis"]
        compatible_spatial = args.format == "source" and source_info.get("source_codec") == "av3a"
        preserve_source = args.format == "source" and not compatible_spatial
        output_ext = ".flac" if compatible_spatial else source_extension(source_info) if preserve_source else f".{args.format}"
        output_audio = audio_dir / f"{stem} [{safe_name(quality_label, '品质未知')}]{output_ext}"
        ready_audio = ready_dir / output_audio.name
        record = {"song_id": song_id, "title": title, "artist": artist, "album": album,
                  "album_id": album_id,
                  "cache_file": cache_file.name, "cache_variants": [p.name for p in variants],
                  "audio_path": str(output_audio), "ready_to_upload_path": str(ready_audio),
                  "quality_label": quality_label, "quality_basis": quality_reason,
                  "status": "pending", "error": ""}
        record.update(source_info)
        record.update(quality_evidence)
        record["measured_quality_estimate"] = measured_quality
        try:
            if quality_label == "品质未知" and not decoded.exists():
                raise RuntimeError(quality_reason)
            pause_checkpoint()
            if args.force or not output_audio.exists() or output_audio.stat().st_size < 4096:
                if compatible_spatial:
                    originals = output / "originals"
                    originals.mkdir(exist_ok=True)
                    original = originals / f"{song_id}.m4a"
                    shutil.copy2(decoded, original)
                    record["original_audio_path"] = str(original)
                    record["playback_note"] = "AV3A 源已保留；兼容播放版本为立体声 FLAC"
                if preserve_source:
                    # XOR decoding restores the exact cached container bytes; do not
                    # downmix, resample, attenuate, or re-encode the source audio.
                    shutil.copy2(decoded, output_audio)
                else:
                    pause_checkpoint()
                # Keep peaks above 0 dBFS in floating point until we can measure them.
                if not preserve_source:
                    temp_mp3 = temp_dir / f"{song_id}-float.wav"
                    decode_cmd = ([str(args.mpv), "-v", "error", "-y", "-i", str(decoded),
                                   "-vn", "-ac", "2", "-c:a", "pcm_f32le", str(temp_mp3)]
                                  if sys.platform == "darwin" else
                                  [str(args.mpv), "--no-config", "--no-video", f"--o={temp_mp3}", "--of=wav",
                                   "--oac=pcm_f32le", "--audio-channels=stereo",
                                   "--msg-level=all=warn", str(decoded)])
                    converted = run(decode_cmd, args.mpv.parent, 900)
                    if converted.returncode or not temp_mp3.exists() or temp_mp3.stat().st_size < 4096:
                        raise RuntimeError(converted.stderr.strip()[-1200:] or "mpv conversion failed")
                    pause_checkpoint()
                    measured = run([str(args.ffmpeg), "-hide_banner", "-nostats", "-i", str(temp_mp3),
                                    "-af", "astats=metadata=0:reset=0", "-f", "null", os.devnull], args.ffmpeg.parent, 900)
                    peaks = re.findall(r"Peak level dB:\s*([-+0-9.eE]+)", measured.stderr)
                    if measured.returncode or not peaks:
                        raise RuntimeError("Could not measure decoded audio peak; conversion stopped")
                    peak_db = max(float(x) for x in peaks)
                    attenuation_db = max(0.0, peak_db + 1.0)
                    record.update({"decoded_peak_dbfs": round(peak_db, 3), "attenuation_db": round(attenuation_db, 3)})
                    print(f"  峰值 {peak_db:.2f} dBFS；降低 {attenuation_db:.2f} dB 避免削波", flush=True)

                    pause_checkpoint()
                    cover_path = cover_dir / f"{song_id}.jpg"
                    got_cover = fetch_cover(text_value(meta.get("pic")), cover_path, args.ffprobe)
                    tagged = temp_dir / f"{song_id}-tagged{output_ext}"
                    cmd = [str(args.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(temp_mp3)]
                    if got_cover:
                        cmd += ["-i", str(cover_path), "-map", "0:a", "-map", "1:v", "-c:v", "mjpeg",
                                "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
                    else:
                        cmd += ["-map", "0:a"]
                    cmd += ["-af", f"volume=-{attenuation_db:.4f}dB", "-c:a", "libmp3lame" if args.format == "mp3" else "flac"]
                    if args.format == "mp3":
                        cmd += ["-b:a", "320k", "-id3v2_version", "3"]
                    cmd += ["-metadata", f"title={title}",
                            "-metadata", f"artist={artist}", "-metadata", f"album={album}",
                            "-metadata", f"comment=网易云音质推定：{quality_label}；{quality_reason}", str(tagged)]
                    tagged_result = run(cmd, args.ffmpeg.parent, 120)
                    if tagged_result.returncode or not tagged.exists():
                        raise RuntimeError(tagged_result.stderr.strip()[-1200:] or "ID3 tagging failed")
                    tagged.replace(output_audio)
                    temp_mp3.unlink(missing_ok=True)
            verified = probe_audio(args.ffprobe, output_audio)
            prepare_upload_audio(output_audio, ready_audio)
            record.update({"status": "ready", "output_duration_seconds": verified["duration_seconds"],
                           "output_format": output_ext.lstrip(".").upper(), "output_codec": verified["source_codec"],
                           "output_bytes": output_audio.stat().st_size})
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
            print(f"  转换失败：{exc}", flush=True)
        finally:
            if not args.keep_decoded:
                decoded.unlink(missing_ok=True)
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
