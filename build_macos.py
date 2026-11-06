"""Build a self-contained macOS app using the pinned relocatable AV3A FFmpeg bundle."""
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from app_version import VERSION, NUMERIC_VERSION

ROOT = Path(__file__).resolve().parent
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
run("bash", ROOT / "build_encoder_macos.sh", stage)
encoder = stage / "encoder/bin/ffmpeg"
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
iconset = stage / "ShengXia.iconset"
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        suffix = "@2x" if scale == 2 else ""
        run("sips", "-z", size * scale, size * scale, ROOT / "assets/shengxia.png",
            "--out", iconset / f"icon_{size}x{size}{suffix}.png")
icon = stage / "ShengXia.icns"
run("iconutil", "-c", "icns", iconset, "-o", icon)
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
    "--copy-metadata", "mutagen", "--copy-metadata", "pycryptodome",
    "--name", "NCM Converter", "--icon", icon, "--osx-bundle-identifier", "com.shengxia.cacheconverter",
    "--distpath", stage / "dist", "--workpath", stage / "pyinstaller", "--specpath", stage,
    "--add-data", f"{licenses}:licenses",
    "--add-data", f"{ROOT / 'assets/shengxia.png'}:assets", ROOT / "gui.py")
app = stage / "dist/NCM Converter.app"
# Keep each relocatable tool dependency tree intact; never flatten same-name dylibs.
run("ditto", tools, app / "Contents/Resources/tools/ffmpeg")
run("ditto", stage / "encoder", app / "Contents/Resources/tools/encoder")
plist_path = app / "Contents/Info.plist"
with plist_path.open("rb") as f:
    info = plistlib.load(f)
info.update({"CFBundleDisplayName": "NCM Converter", "CFBundleShortVersionString": NUMERIC_VERSION,
             "CFBundleVersion": "20001", "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "15.0"})
with plist_path.open("wb") as f:
    plistlib.dump(info, f)
run("codesign", "--force", "--deep", "--sign", "-", app)
run("codesign", "--verify", "--deep", "--strict", app)
smoke_env = dict(os.environ, SHENGXIA_SMOKE_TEST="1")
subprocess.run([str(app / "Contents/MacOS/NCM Converter")], env=smoke_env, check=True, timeout=30)
run(sys.executable, ROOT / "verify_bundle.py", "--app", app / "Contents/MacOS/NCM Converter",
    "--ffmpeg", encoder, "--work", stage / "bundle-check")
for binary in app.glob("Contents/Resources/tools/**/ffmpeg"):
    if binary.is_file():
        run(binary, "-version")
for binary in app.glob("Contents/Resources/tools/**/ffprobe"):
    if binary.is_file():
        run(binary, "-version")
image = stage / "image"
image.mkdir(exist_ok=True)
run("ditto", app, image / "NCM Converter.app")
applications = image / "Applications"
if not applications.exists():
    applications.symlink_to("/Applications")
out = ROOT / "artifacts"
out.mkdir(exist_ok=True)
dmg = out / f"NCM-Converter-{VERSION}-macOS-{ARCH}.dmg"
run("hdiutil", "create", "-volname", "NCM Converter", "-srcfolder", image, "-ov", "-format", "UDZO", dmg)
run("hdiutil", "verify", dmg)
print(f"Built {dmg}")
