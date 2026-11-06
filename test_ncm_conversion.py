"""Optional end-to-end checks: set FFMPEG_BIN_DIR to run against real tools."""
import base64
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mutagen.flac import FLAC
from mutagen.id3 import ID3
from process_ncm import main
from test_ncm_decoder import make_ncm


@unittest.skipUnless(os.environ.get("FFMPEG_BIN_DIR"), "Set FFMPEG_BIN_DIR for audio integration tests")
class ConversionTests(unittest.TestCase):
    def test_formats_tags_cover_skip_and_failure_isolation(self):
        tools = Path(os.environ["FFMPEG_BIN_DIR"])
        ffmpeg = tools / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        ffprobe = tools / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "下载文件"
            source.mkdir()
            cover = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7mQAAAAASUVORK5CYII=")
            for ext in ("mp3", "flac"):
                raw = root / ("sine." + ext)
                subprocess.run([str(ffmpeg), "-v", "error", "-y", "-f", "lavfi", "-i",
                                "sine=frequency=440:duration=0.2", str(raw)], check=True)
                (source / ("下载." + ext + ".ncm")).write_bytes(make_ncm(
                    raw.read_bytes(), {"musicName": "同名歌曲", "artist": [["歌手", 1]],
                                       "album": "测试专辑", "format": ext}, cover))
            (source / "损坏.ncm").write_bytes(b"broken")
            for mode in ("source", "mp3", "flac"):
                args = SimpleNamespace(source=source, output=root / mode, limit=0, format=mode,
                                       force=False, ffmpeg=ffmpeg, ffprobe=ffprobe)
                with contextlib.redirect_stdout(io.StringIO()), patch("urllib.request.urlopen", side_effect=AssertionError("NCM must stay offline")):
                    self.assertEqual(main(args), 1)
                records = json.loads((args.output / "catalog.json").read_text(encoding="utf-8"))["tracks"]
                ready = [r for r in records if r["status"] == "ready"]
                self.assertEqual(len(ready), 2)
                for track in ready:
                    audio = Path(track["audio_path"])
                    if audio.suffix == ".mp3":
                        tags = ID3(audio)
                        self.assertEqual(str(tags["TIT2"]), "同名歌曲")
                        self.assertEqual(tags.getall("APIC")[0].data, cover)
                    else:
                        tags = FLAC(audio)
                        self.assertEqual(tags["title"], ["同名歌曲"])
                        self.assertEqual(tags.pictures[0].data, cover)
                    self.assertTrue(Path(track["ready_to_upload_path"]).exists())
                    if mode == "source":
                        original = root / ("sine.mp3" if track["source_file"].endswith("mp3.ncm") else "sine.flac")
                        def signal(path):
                            return subprocess.run([str(ffmpeg), "-v", "error", "-i", str(path),
                                                   "-map", "0:a:0", "-f", "f32le", "-"],
                                                  capture_output=True, check=True).stdout
                        self.assertEqual(signal(original), signal(audio))
                # Re-running without --force preserves completed audio files.
                mtimes = {r["audio_path"]: Path(r["audio_path"]).stat().st_mtime_ns for r in ready}
                with contextlib.redirect_stdout(io.StringIO()):
                    main(args)
                self.assertTrue(all(Path(p).stat().st_mtime_ns == stamp for p, stamp in mtimes.items()))


if __name__ == "__main__":
    unittest.main()
