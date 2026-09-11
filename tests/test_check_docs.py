"""Regression tests and negative controls for the offline documentation checker."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_docs import check_markdown, check_svg, link_targets


class DocumentationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.note = self.root / "note.md"
        self.asset = self.root / "card.svg"
        self.asset.write_text("asset", encoding="utf-8")

    def markdown(self, text):
        self.note.write_text(text, encoding="utf-8")
        return check_markdown(self.note, self.root)

    def svg(self, body="", attrs="", metadata=True):
        header = '<title id="t">Title</title><desc>Description</desc>' if metadata else ""
        self.asset.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
            f'{attrs}>{header}{body}</svg>', encoding="utf-8"
        )
        return check_svg(self.asset)

    def test_inline_and_reference_links(self):
        self.assertEqual(self.markdown('[asset](card.svg)\n[card]: card.svg "title"'), [])

    def test_missing_target_fails(self):
        self.assertIn("missing local target", self.markdown("[broken](missing.md)")[0])

    def test_html_and_srcset(self):
        self.assertEqual(self.markdown('<picture><source srcset="card.svg 1x, card.svg 2x"><img src="card.svg"></picture>'), [])
        self.assertTrue(self.markdown('<source srcset="missing.svg">'))

    def test_remote_urls_and_fragments_are_not_crawled(self):
        self.assertEqual(self.markdown('[remote](https://example.invalid/a) [fragment](#heading) [relative](//example.invalid/a) [email](mailto:a@example.invalid)'), [])

    def test_code_and_comments_are_ignored(self):
        text = '<!-- [x](absent) -->\n`[x](absent)`\n```md\n[x](absent)\n```\n~~~\n[x](absent)\n~~~\n[yes](card.svg)'
        self.assertEqual(link_targets(text), ["card.svg"])

    def test_nested_fence_does_not_end_example(self):
        self.assertEqual(link_targets('````md\n```\n[x](absent)\n```\n````\n[yes](card.svg)'), ["card.svg"])

    def test_angle_targets_titles_and_encoded_paths(self):
        (self.root / "a b.md").touch()
        self.assertEqual(self.markdown('[one](<a b.md> "title") [two](a%20b.md#heading)'), [])

    def test_parentheses_and_root_relative_paths(self):
        (self.root / "a(b).md").touch()
        self.assertEqual(self.markdown('[one](a(b).md) [two](/card.svg)'), [])

    def test_parent_relative_target(self):
        sub = self.root / "notes"
        sub.mkdir()
        self.note = sub / "note.md"
        self.assertEqual(self.markdown("[asset](../card.svg)"), [])

    def test_escape_outside_repository_fails(self):
        self.assertIn("escapes", self.markdown("[escape](../outside.md)")[0])
        self.assertIn("escapes", self.markdown("[escape](%2e%2e/outside.md)")[0])

    def test_plain_svg_and_internal_gradients(self):
        self.assertEqual(self.svg('<defs><linearGradient id="g"/></defs><path fill="url(#g)"/>', 'aria-labelledby="t"'), [])

    def test_svg_metadata_and_definitions(self):
        self.assertEqual(len(self.svg(metadata=False)), 2)
        self.assertTrue(self.svg('<path fill="url(#absent)"/>'))
        self.assertTrue(self.svg(attrs='aria-labelledby="missing"'))

    def test_svg_active_content_fails(self):
        for body in ('<script/>', '<foreignObject/>', '<animate/>', '<style/>'):
            with self.subTest(body=body):
                self.assertTrue(self.svg(body))
        self.assertTrue(self.svg(attrs='onload="alert(1)"'))

    def test_svg_external_content_fails(self):
        for body in ('<image href="https://example.invalid/x"/>', '<path fill="url(https://example.invalid/x)"/>'):
            with self.subTest(body=body):
                self.assertTrue(self.svg(body))

    def test_svg_bad_xml_and_dtd_fail(self):
        self.asset.write_text("<svg>", encoding="utf-8")
        self.assertTrue(check_svg(self.asset))
        self.asset.write_text('<!DOCTYPE svg><svg/>', encoding="utf-8")
        self.assertTrue(check_svg(self.asset))


if __name__ == "__main__":
    unittest.main()
