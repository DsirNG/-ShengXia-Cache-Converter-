#!/bin/bash
set -euo pipefail
stage="$1"
mkdir -p "$stage/src" "$stage/static" "$stage/encoder"
curl -fL --retry 3 https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz -o "$stage/ffmpeg-src.tar.xz"
tar -xf "$stage/ffmpeg-src.tar.xz" -C "$stage/src"
lame="$(brew --prefix lame)"
cp "$lame/lib/libmp3lame.a" "$stage/static/"
cd "$stage/src/ffmpeg-9.0.2"
./configure --prefix="$stage/encoder" --disable-everything --disable-autodetect \
  --disable-doc --disable-debug --disable-shared --enable-static --enable-ffmpeg \
  --enable-libmp3lame --enable-zlib --extra-cflags="-I$lame/include" --extra-ldflags="-L$stage/static" \
  --enable-protocol=file,pipe --enable-demuxer=wav,image2,jpeg_pipe,png_pipe,mjpeg \
  --enable-decoder=pcm_f32le,pcm_s16le,pcm_s24le,pcm_s32le,mjpeg,png \
  --enable-encoder=flac,libmp3lame,mjpeg,pcm_s16le --enable-parser=mjpeg,png \
  --enable-muxer=mp3,flac,null --enable-filter=astats,volume,aresample,aformat,anull,null,format,scale
make -j3
cp ffmpeg "$stage/encoder/ffmpeg"
cp COPYING.LGPLv2.1 "$stage/encoder/FFmpeg-LICENSE"
