import re
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from process_cache import run, fetch_cover


class ToolOutputTests(unittest.TestCase):
    def test_https_initialization_failure_does_not_abort_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            cover = Path(folder) / "cover.jpg"
            cover.write_bytes(b"old cover")
            with patch("process_cache.urllib.request.build_opener",
                       side_effect=OSError(42, "Illegal byte sequence")):
                self.assertFalse(fetch_cover(
                    "https://api.injahow.cn/meting/?type=pic", cover, Path("ffprobe.exe")))
            self.assertFalse(cover.exists())

    def test_utf8_paths_and_invalid_bytes_preserve_peak_log(self):
        # Reproduce a tool log containing a Chinese path and an undecodable byte.
        code = (
            "import sys; "
            "sys.stdout.buffer.write(b'{\"streams\": []}'); "
            "sys.stderr.buffer.write("
            "'Input: 声匣转换结果\\nPeak level dB: 1.25\\n'.encode('utf-8') + b'\\xff')"
        )
        result = run([sys.executable, "-c", code], Path(__file__).parent, 10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '{"streams": []}')
        self.assertIn("声匣转换结果", result.stderr)
        self.assertIn("\ufffd", result.stderr)
        self.assertEqual(re.findall(r"Peak level dB:\s*([-+0-9.eE]+)", result.stderr), ["1.25"])

    def test_failed_tool_keeps_diagnostic_and_exit_code(self):
        result = run([sys.executable, "-c",
                      "import sys; sys.stderr.buffer.write(b'bad input\\xff'); sys.exit(2)"],
                     Path(__file__).parent, 10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("bad input", result.stderr)


if __name__ == "__main__":
    unittest.main()
