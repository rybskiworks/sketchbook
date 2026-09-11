"""Negative controls added after reviewing the initial curation checker."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_docs import check_markdown, check_svg


class CheckerRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.note = self.root / "note.md"
        self.target = self.root / "target.md"
        self.note.write_text("[target](target.md)", encoding="utf-8")
        self.target.write_text("# Target\n", encoding="utf-8")

    def test_tracked_target_passes(self):
        self.assertEqual(check_markdown(self.note, self.root, frozenset({self.note, self.target})), [])

    def test_existing_untracked_target_fails(self):
        errors = check_markdown(self.note, self.root, frozenset({self.note}))
        self.assertTrue(any("not Git-tracked" in error for error in errors))

    def test_directory_with_tracked_descendant_passes(self):
        folder = self.root / "explorations"
        folder.mkdir()
        child = folder / "one.md"
        child.touch()
        self.note.write_text("[notes](explorations/)", encoding="utf-8")
        self.assertEqual(check_markdown(self.note, self.root, frozenset({self.note, child})), [])

    def test_empty_untracked_directory_fails(self):
        (self.root / "empty").mkdir()
        self.note.write_text("[empty](empty/)", encoding="utf-8")
        self.assertTrue(check_markdown(self.note, self.root, frozenset({self.note})))

    def test_git_metadata_is_not_a_documentation_target(self):
        metadata = self.root / ".git"
        metadata.mkdir()
        (metadata / "config").touch()
        self.note.write_text("[metadata](.git/config)", encoding="utf-8")
        self.assertTrue(check_markdown(self.note, self.root, frozenset({self.note})))

    def test_markdown_symlink_source_is_rejected(self):
        alias = self.root / "alias.md"
        alias.symlink_to(self.note)
        self.assertTrue(any("symlink" in error for error in check_markdown(alias, self.root)))

    def test_symlink_target_is_rejected(self):
        alias = self.root / "alias.md"
        alias.symlink_to(self.target)
        self.note.write_text("[alias](alias.md)", encoding="utf-8")
        self.assertTrue(any("symlink" in error for error in check_markdown(self.note, self.root)))

    def test_symlink_directory_target_is_rejected(self):
        folder = self.root / "real"
        folder.mkdir()
        (folder / "child.md").touch()
        (self.root / "alias").symlink_to(folder, target_is_directory=True)
        self.note.write_text("[alias](alias/child.md)", encoding="utf-8")
        self.assertTrue(any("symlink" in error for error in check_markdown(self.note, self.root)))

    def svg(self, box="0 0 10 10", body=""):
        path = self.root / "card.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="{box}"><title>T</title><desc>D</desc>{body}</svg>',
            encoding="utf-8",
        )
        return check_svg(path)

    def test_non_finite_viewbox_values_fail(self):
        for box in ("nan 0 10 10", "0 inf 10 10", "0 0 inf 10", "0 0 10 inf"):
            with self.subTest(box=box):
                self.assertTrue(self.svg(box))

    def test_missing_direct_svg_reference_fails(self):
        for attr in ("href", "xlink:href"):
            with self.subTest(attr=attr):
                self.assertTrue(self.svg(body=f'<use {attr}="#absent"/>'))

    def test_valid_direct_svg_reference_passes(self):
        self.assertEqual(self.svg(body='<defs><path id="p"/></defs><use href="#p"/>'), [])

    def test_svg_symlink_source_is_rejected(self):
        self.svg()
        alias = self.root / "alias.svg"
        alias.symlink_to(self.root / "card.svg")
        self.assertTrue(any("symlink" in error for error in check_svg(alias)))

    def test_cli_rejects_untracked_target_then_accepts_staged_target(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        source = Path(__file__).resolve().parents[1] / "scripts/check_docs.py"
        shutil.copy2(source, scripts / "check_docs.py")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "note.md", "scripts/check_docs.py"], cwd=self.root, check=True)
        command = ["python3", "scripts/check_docs.py"]
        bad = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("not Git-tracked", bad.stderr)
        subprocess.run(["git", "add", "target.md"], cwd=self.root, check=True)
        good = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)


if __name__ == "__main__":
    unittest.main()
