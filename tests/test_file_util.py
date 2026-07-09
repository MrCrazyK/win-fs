import codecs
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "file_util.py"
TMP_ROOT = ROOT / "tmp" / "tests"


class FileUtilCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.case_dir = TMP_ROOT / self._testMethodName
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def test_script_file_has_no_utf8_bom(self):
        self.assertFalse(SCRIPT.read_bytes().startswith(codecs.BOM_UTF8))

    def test_read_command_survives_gbk_stdout(self):
        source = self.case_dir / "中文.txt"
        source.write_text("中文 ✅\n", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "gbk"

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "read", str(source)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn("中文", result.stdout.decode("utf-8", "replace"))
        self.assertIn("✅", result.stdout.decode("utf-8", "replace"))

    def test_search_skips_binary_files(self):
        root = self.case_dir
        (root / "ok.txt").write_text("needle\n", encoding="utf-8")
        (root / "bad.bin").write_bytes(b"\x00\xffneedle\x00")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "needle"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok.txt", result.stdout)
        self.assertNotIn("bad.bin", result.stdout)

    def test_search_excludes_common_noise_dirs_by_default(self):
        root = self.case_dir
        (root / "src").mkdir(exist_ok=True)
        (root / "src" / "ok.txt").write_text("needle\n", encoding="utf-8")
        (root / ".git").mkdir(exist_ok=True)
        (root / ".git" / "packed-refs").write_text("needle\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "needle"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok.txt", result.stdout)
        self.assertNotIn("packed-refs", result.stdout)


if __name__ == "__main__":
    unittest.main()
