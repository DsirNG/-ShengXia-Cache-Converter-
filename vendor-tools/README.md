# Build tools

The program installer bundles Yaoplayer/mpv and FFmpeg. These binaries are intentionally not committed to this source repository because they add hundreds of megabytes and have separate upstream licensing terms.

For a local build, obtain an AV3A-capable core that contains `Yaoplayer.com`, and an FFmpeg `bin` directory containing `ffmpeg.exe` and `ffprobe.exe`. Pass their paths to `build.ps1` or set `MPV_CORE_DIR` and `FFMPEG_BIN_DIR`.

The installer is built with Inno Setup 7. Download it from the official [Inno Setup downloads page](https://jrsoftware.org/isdl.php), then pass the path to `ISCC.exe` or set `INNO_SETUP_COMPILER`.
