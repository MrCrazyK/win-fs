import codecs
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "file_util.py"
PREFLIGHT = ROOT / "scripts" / "preflight.py"
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

    def test_read_supports_start_and_end_line(self):
        source = self.case_dir / "lines.txt"
        source.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "read", str(source), "--start-line", "2", "--end-line", "3"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "two\nthree\n\n")

    def test_search_supports_include_and_exclude_dirs(self):
        root = self.case_dir
        (root / "src").mkdir(exist_ok=True)
        (root / "docs").mkdir(exist_ok=True)
        (root / "src" / "hit.txt").write_text("dir-filter-token\n", encoding="utf-8")
        (root / "docs" / "skip.txt").write_text("dir-filter-token\n", encoding="utf-8")

        include_result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "dir-filter-token", "--include-dir", "src"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        exclude_result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "dir-filter-token", "--exclude-dir", "docs"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(include_result.returncode, 0, include_result.stderr)
        self.assertIn("hit.txt", include_result.stdout)
        self.assertNotIn("skip.txt", include_result.stdout)
        self.assertEqual(exclude_result.returncode, 0, exclude_result.stderr)
        self.assertIn("hit.txt", exclude_result.stdout)
        self.assertNotIn("skip.txt", exclude_result.stdout)

    def test_search_respects_max_file_size(self):
        root = self.case_dir
        (root / "small.txt").write_text("size-token\n", encoding="utf-8")
        (root / "large.txt").write_text("x" * 100 + "size-token\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "size-token", "--max-file-size", "20"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("small.txt", result.stdout)
        self.assertNotIn("large.txt", result.stdout)

    def test_write_supports_atomic_and_backup(self):
        target = self.case_dir / "write.txt"
        target.write_text("old\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "write", str(target), "--content", "new\n", "--atomic", "--backup"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
        self.assertEqual((self.case_dir / "write.txt.bak").read_text(encoding="utf-8"), "old\n")

    def test_replace_supports_backup(self):
        target = self.case_dir / "replace.txt"
        target.write_text("before before\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "replace", str(target), "before", "after", "--backup"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "after after\n")
        self.assertEqual((self.case_dir / "replace.txt.bak").read_text(encoding="utf-8"), "before before\n")

    def test_info_reports_bom_newline_and_sha256(self):
        target = self.case_dir / "meta.txt"
        target.write_bytes(codecs.BOM_UTF8 + "a\r\nb\r\n".encode("utf-8"))

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "info", str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout)
        self.assertEqual(info["bom"], "utf-8")
        self.assertEqual(info["newline"], "crlf")
        self.assertRegex(info["sha256"], r"^[0-9a-f]{64}$")

    def test_search_supports_jsonl_output(self):
        root = self.case_dir
        (root / "a.txt").write_text("jsonl-token\n", encoding="utf-8")
        (root / "b.txt").write_text("jsonl-token\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "search", str(root), "jsonl-token", "--jsonl"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(all("file" in item and "line" in item for item in lines))

    def test_preflight_script_checks_bom_without_running_tests(self):
        result = subprocess.run(
            [sys.executable, str(PREFLIGHT), "--skip-tests"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BOM check passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
