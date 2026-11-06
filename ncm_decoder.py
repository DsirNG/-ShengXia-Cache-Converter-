"""Local NCM decoder ported from DsirNG/aural-music public/api/ncm.js.

Only the container encryption is removed; audio is not re-encoded here.
"""
import base64
import json
import struct

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

CORE_KEY = b"hzHRAmso5kInbaxW"
META_KEY = b"#14ljk_!\\]&0U<'("


def decrypt_block(data, key):
    try:
        return unpad(AES.new(key, AES.MODE_ECB).decrypt(data), 16)
    except ValueError as exc:
        raise ValueError("NCM 密钥或填充无效") from exc


def read_header(reader):
    def take(size):
        if size > 16 * 1024 * 1024:
            raise ValueError("NCM 头部字段过大")
        data = reader.read(size)
        if len(data) != size:
            raise ValueError("NCM 文件不完整或长度字段无效")
        return data

    def length():
        return struct.unpack("<I", take(4))[0]

    if take(8) != b"CTENFDAM":
        raise ValueError("不是有效的 NCM 文件")
    take(2)
    key = decrypt_block(bytes(x ^ 100 for x in take(length())), CORE_KEY)[17:]
    if not key:
        raise ValueError("NCM 音频密钥为空")
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + key[i % len(key)]) & 255
        box[i], box[j] = box[j], box[i]
    stream = bytes(box[(box[(i + 1) & 255] +
                        box[((i + 1) + box[(i + 1) & 255]) & 255]) & 255]
                   for i in range(256))
    metadata = {}
    raw = take(length())
    if raw:
        raw = bytes(x ^ 99 for x in raw)
        try:
            text = decrypt_block(base64.b64decode(raw[22:], validate=True), META_KEY).decode("utf-8")
            kind, payload = text.split(":", 1)
            metadata = json.loads(payload)
            if kind == "dj":
                metadata = metadata.get("mainMusic") or {}
            if not isinstance(metadata, dict):
                raise ValueError("歌曲信息必须为对象")
        except (ValueError, UnicodeError, AttributeError) as exc:
            raise ValueError("NCM 歌曲信息无效") from exc
    take(5)
    space, size = length(), length()
    if size > space:
        raise ValueError("NCM 封面长度无效")
    cover = take(space)[:size]
    return stream, metadata, cover


def decode_file(source, destination, checkpoint=lambda: None):
    """Stream the decrypted audio to disk and return embedded metadata/artwork."""
    with source.open("rb") as reader:
        stream, metadata, cover = read_header(reader)
        # A block size divisible by 256 preserves the cipher table position.
        tables = [bytes(x ^ mask for x in range(256)) for mask in stream]
        with destination.open("wb") as writer:
            total = 0
            while chunk := reader.read(1024 * 1024):
                checkpoint()
                output = bytearray(len(chunk))
                for i, table in enumerate(tables):
                    output[i::256] = chunk[i::256].translate(table)
                writer.write(output)
                total += len(chunk)
    if not total:
        raise ValueError("NCM 文件不包含音频")
    return metadata, cover
