"""Build a self-contained macOS app using the pinned relocatable AV3A FFmpeg bundle."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.7"
TAG = "mpv-iina-avs-ffmpeg-9.0.2-mpv-v0.41.0-20261023-033837"
ARCH = platform.machine()
if sys.platform != "darwin" or ARCH != os.environ.get("EXPECTED_ARCH", ARCH):
    raise SystemExit("Build must run on the target macOS architecture")

def run(*args):
    subprocess.run(list(map(str, args)), check=True)

stage = ROOT / "build/macos"
stage.mkdir(parents=True, exist_ok=True)
archive = stage / "ffmpeg.zip"
name = f"ffmpeg-cli-bundle-macos-{ARCH}-gpl-ffmpeg-9.0.2.zip"
url = f"https://github.com/nilaoda/mpv-iina-avs/releases/download/{TAG}/{name}"
urllib.request.urlretrieve(url, archive)
tools = stage / "ffmpeg"
tools.mkdir(exist_ok=True)
run("ditto", "-x", "-k", archive, tools)
ffmpeg, ffprobe = tools / "bin/ffmpeg", tools / "bin/ffprobe"
for tool in (ffmpeg, ffprobe):
    tool.chmod(0o755)
    run(tool, "-version")
encoder = Path(shutil.which("ffmpeg") or "")
if not encoder.is_file():
    raise RuntimeError("Install FFmpeg with libmp3lame before building")
codecs = subprocess.check_output([str(ffmpeg), "-hide_banner", "-decoders"], text=True)
if "av3a" not in codecs.lower():
    raise RuntimeError("AV3A decoder missing")
# Exercise the same conversion pipeline without external metadata requests.
fixture = stage / "fixture.m4a"
run(ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", fixture)
cache = stage / "cache"
cache.mkdir(exist_ok=True)
raw = fixture.read_bytes()
md5 = hashlib.md5(raw).hexdigest()
source = cache / f"1-320-{md5}.uc"
source.write_bytes(bytes(v ^ 0xA3 for v in raw))
source.with_suffix(".info").write_text(json.dumps({"md5": md5, "size": len(raw), "level": "exhigh"}))
for mode in ("source", "mp3", "flac"):
    output = stage / ("check-" + mode)
    meta = output / "work/metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "1.json").write_text(json.dumps({"name": "Fixture", "artist": "CI", "album": "CI"}))
    run(sys.executable, ROOT / "process_cache.py", "--source", cache, "--output", output,
        "--format", mode, "--mpv", ffmpeg, "--ffmpeg", encoder, "--ffprobe", ffprobe, "--force")
    track = json.loads((output / "catalog.json").read_text())["tracks"][0]
    assert track["status"] == "ready" and track["quality_status"] == "confirmed"
    run(ffmpeg, "-v", "error", "-i", track["audio_path"], "-f", "null", "-")
# Tk initialization catches missing Tcl/Tk linkage before packaging.
run(sys.executable, "-c", "import tkinter as tk; w=tk.Tk(); w.update(); w.destroy()")
licenses = stage / "licenses"
licenses.mkdir(exist_ok=True)
(licenses / "macOS-tools.txt").write_text(f"FFmpeg/AV3A bundle: {url}\nSources/build scripts: https://github.com/nilaoda/mpv-iina-avs/tree/{TAG}\nAV3A SDK upstream notes research/education-only restrictions; see upstream README.\n")
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
    "--name", "ShengXia", "--osx-bundle-identifier", "com.shengxia.cacheconverter",
    "--distpath", stage / "dist", "--workpath", stage / "pyinstaller", "--specpath", stage,
    "--add-binary", f"{encoder}:tools/encoder",
    "--add-data", f"{tools}:tools/ffmpeg", "--add-data", f"{licenses}:licenses",
    "--add-data", f"{ROOT / 'assets/shengxia.png'}:assets", ROOT / "gui.py")
app = stage / "dist/ShengXia.app"
run("codesign", "--force", "--deep", "--sign", "-", app)
run("codesign", "--verify", "--deep", "--strict", app)
smoke_env = dict(os.environ, SHENGXIA_SMOKE_TEST="1")
subprocess.run([str(app / "Contents/MacOS/ShengXia")], env=smoke_env, check=True, timeout=30)
for binary in app.glob("Contents/Resources/tools/**/ffmpeg"):
    if binary.is_file():
        run(binary, "-version")
for binary in app.glob("Contents/Resources/tools/**/ffprobe"):
    if binary.is_file():
        run(binary, "-version")
image = stage / "image"
image.mkdir(exist_ok=True)
run("ditto", app, image / "ShengXia.app")
applications = image / "Applications"
if not applications.exists():
    applications.symlink_to("/Applications")
out = ROOT / "artifacts"
out.mkdir(exist_ok=True)
dmg = out / f"ShengXia-{VERSION}-macOS-{ARCH}.dmg"
run("hdiutil", "create", "-volname", "ShengXia", "-srcfolder", image, "-ov", "-format", "UDZO", dmg)
print(f"Built {dmg}")
