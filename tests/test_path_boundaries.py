"""Path-boundary regressions from the governance follow-up review."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_docs import check_markdown, check_svg

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><title>T</title><desc>D</desc></svg>'


class PathBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.note = self.root / "note.md"
        self.note.write_text("# Note\n", encoding="utf-8")

    def test_cyclic_link_is_reported_without_an_exception(self):
        (self.root / "loop.md").symlink_to("loop.md")
        self.note.write_text("[loop](loop.md)", encoding="utf-8")
        self.assertIn("symlink", " ".join(check_markdown(self.note, self.root)))

    def test_symlink_target_is_rejected_before_resolution(self):
        alias = self.root / "alias.md"
        alias.symlink_to(self.note)
        self.note.write_text("[alias](alias.md)", encoding="utf-8")
        original = Path.resolve
        resolved = []

        def record(path, *args, **kwargs):
            resolved.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", record):
            self.assertIn("symlink", " ".join(check_markdown(self.note, self.root)))
        self.assertNotIn(alias, resolved)

    def test_target_resolution_error_is_a_diagnostic(self):
        target = self.root / "target.md"
        target.touch()
        self.note.write_text("[target](target.md)", encoding="utf-8")
        original = Path.resolve

        for error in (OSError("unreadable path"), RuntimeError("unresolvable path")):
            with self.subTest(error=type(error).__name__):
                def fail_target(path, *args, **kwargs):
                    if path == target:
                        raise error
                    return original(path, *args, **kwargs)

                with patch.object(Path, "resolve", fail_target):
                    self.assertIn("invalid local target", " ".join(check_markdown(self.note, self.root)))

    def test_svg_parent_symlink_is_rejected_before_read(self):
        real = self.root / "real"
        real.mkdir()
        (real / "card.svg").write_text(SVG, encoding="utf-8")
        alias = self.root / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with patch.object(Path, "read_text", side_effect=AssertionError("followed a symlink")):
            self.assertIn("symlink", " ".join(check_svg(alias / "card.svg")))

    def test_svg_cyclic_parent_is_reported_without_an_exception(self):
        alias = self.root / "loop"
        alias.symlink_to("loop", target_is_directory=True)
        self.assertIn("symlink", " ".join(check_svg(alias / "card.svg")))

    def cli_repo(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(Path(__file__).resolve().parents[1] / "scripts/check_docs.py", scripts)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def run_cli(self):
        return subprocess.run(
            [sys.executable, "scripts/check_docs.py"], cwd=self.root,
            capture_output=True, text=True, timeout=10,
        )

    def test_cli_accepts_regular_tracked_svg(self):
        self.cli_repo()
        (self.root / "card.svg").write_text(SVG, encoding="utf-8")
        subprocess.run(["git", "add", "note.md", "card.svg", "scripts"], cwd=self.root, check=True)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_rejects_directory_replaced_with_external_symlink(self):
        self.cli_repo()
        assets = self.root / "assets"
        assets.mkdir()
        (assets / "card.svg").write_text(SVG, encoding="utf-8")
        subprocess.run(["git", "add", "assets", "scripts"], cwd=self.root, check=True)
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            (outside / "card.svg").write_text(SVG, encoding="utf-8")
            shutil.rmtree(assets)
            assets.symlink_to(outside, target_is_directory=True)
            result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("symlink", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_loop_without_traceback(self):
        self.cli_repo()
        self.note.write_text("[loop](loop.md)", encoding="utf-8")
        (self.root / "loop.md").symlink_to("loop.md")
        subprocess.run(["git", "add", "note.md", "scripts"], cwd=self.root, check=True)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("symlink", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
