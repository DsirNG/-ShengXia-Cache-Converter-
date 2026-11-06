"""Batch conversion of downloaded NCM files, using the AURAL decoder logic."""
import json
import hashlib
import tempfile
import traceback
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError

from ncm_decoder import decode_file
from process_cache import safe_name, text_value, run, probe_audio, prepare_upload_audio, source_extension


def write_tags(path, metadata, cover):
    title = text_value(metadata.get("musicName"))
    artists = metadata.get("artist") or []
    artists = [text_value(a[0]) for a in artists if isinstance(a, list) and a]
    album = text_value(metadata.get("album"))
    mime = "image/png" if cover.startswith(b"\x89PNG") else "image/jpeg"
    if path.suffix == ".mp3":
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        for key, value in ((TIT2, title), (TPE1, artists), (TALB, album)):
            if value:
                tags.add(key(encoding=3, text=value))
        if cover:
            tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover))
        tags.save(path, v2_version=3)
    elif path.suffix == ".flac":
        tags = FLAC(path)
        for key, value in (("title", title), ("artist", artists), ("album", album)):
            if value:
                tags[key] = value
        if cover:
            picture = Picture()
            picture.type, picture.mime, picture.data = 3, mime, cover
            tags.clear_pictures()
            tags.add_picture(picture)
        tags.save()


def main(args, checkpoint=lambda: None):
    files = sorted(p for p in args.source.iterdir() if p.is_file() and p.suffix.lower() == ".ncm")
    if not files:
        raise ValueError(f"目录中没有 .ncm 下载文件：{args.source}")
    if args.limit:
        files = files[:args.limit]
    if not args.ffprobe.is_file() or (args.format != "source" and not args.ffmpeg.is_file()):
        raise FileNotFoundError("缺少音频转换工具 ffprobe / ffmpeg")
    output = args.output
    for name in ("audio", "covers", "ready_to_upload", "work"):
        (output / name).mkdir(parents=True, exist_ok=True)
    records = []
    for index, source in enumerate(files, 1):
        checkpoint()
        record = {"input_type": "ncm", "source_file": source.name,
                  "title": source.stem, "artist": "", "status": "pending", "error": "",
                  "quality_label": "下载文件（原始编码）"}
        try:
            with tempfile.TemporaryDirectory(dir=output / "work", prefix="ncm-") as temp:
                raw = Path(temp) / "decoded.audio"
                meta, cover = decode_file(source, raw, checkpoint)
                info = probe_audio(args.ffprobe, raw)
                codec = info["source_codec"]
                if codec not in {"mp3", "flac", "aac", "alac", "vorbis", "opus",
                                 "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"}:
                    raise ValueError(f"暂不支持此 NCM 音频编码：{codec}")
                ext = source_extension(info)
                if args.format != "source":
                    ext = "." + args.format
                title = text_value(meta.get("musicName")) or source.stem
                artists = meta.get("artist") or []
                artist = " / ".join(text_value(a[0]) for a in artists if isinstance(a, list) and a)
                # A source-derived suffix keeps same-title downloads independent.
                stem = safe_name(f"{artist} - {title}" if artist else title, source.stem)
                identity = hashlib.sha256(source.name.encode("utf-8")).hexdigest()[:8]
                destination = output / "audio" / f"{stem} [{identity}]{ext}"
                record.update(info)
                record.update(title=title, artist=artist, album=text_value(meta.get("album")))
                if args.force or not destination.exists():
                    checkpoint()
                    staged = Path(temp) / ("tagged" + ext)
                    if args.format == "source":
                        raw.replace(staged)
                    else:
                        cmd = [str(args.ffmpeg), "-v", "error", "-y", "-i", str(raw),
                               "-map", "0:a:0", "-vn", "-c:a",
                               "libmp3lame" if args.format == "mp3" else "flac"]
                        if args.format == "mp3":
                            cmd += ["-b:a", "320k"]
                        result = run(cmd + [str(staged)], args.ffmpeg.parent, 900)
                        if result.returncode:
                            raise RuntimeError(result.stderr[-1200:])
                    write_tags(staged, meta, cover)
                    probe_audio(args.ffprobe, staged)
                    staged.replace(destination)
                verified = probe_audio(args.ffprobe, destination)
                ready = output / "ready_to_upload" / destination.name
                prepare_upload_audio(destination, ready)
                if cover:
                    image = output / "covers" / (identity + (".png" if cover.startswith(b"\x89PNG") else ".jpg"))
                    image.write_bytes(cover)
                    record["cover_path"] = str(image)
                record.update(status="ready", audio_path=str(destination), ready_to_upload_path=str(ready),
                              output_format=ext[1:].upper(), output_codec=verified["source_codec"],
                              output_bytes=destination.stat().st_size,
                              output_duration_seconds=verified["duration_seconds"])
        except Exception as exc:
            record.update(status="failed", error=str(exc), error_traceback=traceback.format_exc())
            print(f"  转换失败：{exc}", flush=True)
        records.append(record)
        print(f"[{index}/{len(files)}] {record['status']}: {record['title']}", flush=True)
        (output / "catalog.json").write_text(json.dumps(
            {"source": str(args.source), "input_type": "ncm", "tracks": records},
            ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"input_type": "ncm", "source_files": len(files), "processed_files": len(records),
               "ready": sum(r["status"] == "ready" for r in records),
               "failed": sum(r["status"] == "failed" for r in records),
               "output": str(output), "uploaded": False}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(summary["failed"] > 0)
