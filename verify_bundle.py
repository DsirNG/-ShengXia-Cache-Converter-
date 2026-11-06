"""Generate synthetic fixtures and check the shipped app's actual worker."""
import argparse
import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

from test_ncm_decoder import make_ncm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    cache, ncm = args.work / "cache", args.work / "ncm"
    cache.mkdir(exist_ok=True)
    ncm.mkdir(exist_ok=True)
    cover = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7mQAAAAASUVORK5CYII=")
    for fmt in ("mp3", "flac", "m4a"):
        audio = args.work / ("fixture." + fmt)
        subprocess.run([str(args.ffmpeg), "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=0.3", str(audio)], check=True)
        raw = audio.read_bytes()
        if fmt == "m4a":
            md5 = hashlib.md5(raw).hexdigest()
            uc = cache / f"1-320-{md5}.uc"
            uc.write_bytes(bytes(x ^ 0xa3 for x in raw))
            uc.with_suffix(".info").write_text(json.dumps({"md5": md5, "size": len(raw), "level": "exhigh"}))
        else:
            (ncm / f"测试下载-{fmt}.ncm").write_bytes(make_ncm(raw,
                {"musicName": "NCM 测试", "artist": [["CI", 0]], "album": "CI", "format": fmt}, cover))
    env = dict(os.environ, NCM_CONVERTER_SELF_TEST=str(args.work.resolve()))
    result = subprocess.run([str(args.app.resolve())], env=env, timeout=300)
    report = json.loads((args.work / "bundle-report.json").read_text(encoding="utf-8"))
    assert result.returncode == 0 and report["result"] == "passed", report
    print("Frozen app: cache + NCM, source/MP3/FLAC, metadata and artwork checks passed")


if __name__ == "__main__":
    main()
