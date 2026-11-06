import base64
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from ncm_decoder import CORE_KEY, META_KEY, decode_file, read_header


def make_ncm(audio, metadata=None, cover=b"", kind="music"):
    """Create a synthetic container; cipher loop independent of decoder tables."""
    key = b"fixture audio key"
    key_data = AES.new(CORE_KEY, AES.MODE_ECB).encrypt(pad(b"neteasecloudmusic" + key, 16))
    encrypted_key = bytes(x ^ 100 for x in key_data)
    meta_data = b""
    if metadata is not None:
        payload = (kind + ":" + json.dumps(metadata, ensure_ascii=False)).encode("utf-8")
        ciphertext = AES.new(META_KEY, AES.MODE_ECB).encrypt(pad(payload, 16))
        meta_data = bytes(x ^ 99 for x in b"163 key(Don't modify):" + base64.b64encode(ciphertext))
    box = list(range(256))
    previous = 0
    for index in range(256):
        previous = (previous + box[index] + key[index % len(key)]) % 256
        box[index], box[previous] = box[previous], box[index]
    encrypted_audio = bytearray(audio)
    for index in range(len(audio)):
        j = (index + 1) % 256
        encrypted_audio[index] ^= box[(box[j] + box[(box[j] + j) % 256]) % 256]
    length = lambda n: struct.pack("<I", n)
    return (b"CTENFDAM\x00\x00" + length(len(encrypted_key)) + encrypted_key
            + length(len(meta_data)) + meta_data + b"\x00" * 5
            + length(len(cover) + 3) + length(len(cover)) + cover + b"\x00" * 3
            + encrypted_audio)


class NcmTests(unittest.TestCase):
    def test_streaming_roundtrip_metadata_and_cover(self):
        audio = bytes(range(256)) * 4100 + b"tail"
        metadata = {"musicName": "测试歌曲", "artist": [["测试歌手", 1]], "format": "mp3"}
        cover = b"\x89PNG\r\n\x1a\nfixture"
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "下载.ncm", Path(folder) / "decoded.mp3"
            source.write_bytes(make_ncm(audio, metadata, cover))
            result, image = decode_file(source, target)
            self.assertEqual(target.read_bytes(), audio)
            self.assertEqual(result, metadata)
            self.assertEqual(image, cover)

    def test_dj_metadata(self):
        _, meta, _ = read_header(io.BytesIO(make_ncm(b"audio", {"mainMusic": {"musicName": "节目"}}, kind="dj")))
        self.assertEqual(meta["musicName"], "节目")

    def test_bad_or_truncated_header(self):
        for data in (b"not an ncm file", make_ncm(b"audio")[:20],
                     b"CTENFDAM\x00\x00" + struct.pack("<I", 0xffffffff)):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                read_header(io.BytesIO(data))

    def test_bad_cover_length(self):
        data = bytearray(make_ncm(b"audio"))
        key_length = struct.unpack_from("<I", data, 10)[0]
        size_position = 14 + key_length + 4 + 5 + 4
        struct.pack_into("<I", data, size_position, 100)
        with self.assertRaisesRegex(ValueError, "封面"):
            read_header(io.BytesIO(data))


if __name__ == "__main__":
    unittest.main()
