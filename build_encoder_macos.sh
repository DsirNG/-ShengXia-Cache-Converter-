#!/bin/bash
set -euo pipefail
stage="$1"
tag=mpv-iina-avs-ffmpeg-9.0.2-mpv-v0.41.0-20261023-033837
curl -fL --retry 3 "https://raw.githubusercontent.com/nilaoda/mpv-iina-avs/$tag/tools/package_macho_bundle.rb" -o "$stage/package_macho_bundle.rb"
ruby "$stage/package_macho_bundle.rb" "$stage/encoder" "$(brew --prefix)" -- "$(command -v ffmpeg)"
"$stage/encoder/bin/ffmpeg" -version
