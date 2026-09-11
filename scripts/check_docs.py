#!/usr/bin/env python3
"""Offline checks for ordinary local documentation links and self-contained SVGs.

Intentionally not a CommonMark parser, anchor checker, crawler, or sanitizer.
Only Git-tracked Markdown and SVG files are checked by the command-line entrypoint.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SVG = "{http://www.w3.org/2000/svg}"
INLINE_LINK = re.compile(
    r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|(?:\\.|[^()\s\\]|\((?:\\.|[^()\\])*\))+)'  # one nested pair
)
REFERENCE_LINK = re.compile(r'^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)', re.M)


def prose(text: str) -> str:
    """Remove fenced examples, comments, and inline code before extracting links."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]))
        else:
            lines.append(line)
    return re.sub(r"(`+)(?!`).*?(?<!`)\1(?!`)", "", "".join(lines), flags=re.S)


class HTMLLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            if name in {"href", "src"}:
                self.targets.append(value)
            elif name == "srcset":
                # Ordinary repository asset URLs, not data URIs containing commas.
                for candidate in value.split(","):
                    fields = candidate.split()
                    if fields:
                        self.targets.append(fields[0])


def link_targets(text: str) -> list[str]:
    text = prose(text)
    targets = [m[1].strip("<>") for pattern in (INLINE_LINK, REFERENCE_LINK) for m in pattern.finditer(text)]
    html = HTMLLinks()
    html.feed(text)
    return targets + html.targets


def symlink_in_path(path: Path, root: Path) -> bool:
    return any(part.is_symlink() for part in (path, *path.parents)
               if part == root or root in part.parents)


def check_markdown(
    path: Path, root: Path, tracked_paths: frozenset[Path] | None = None,
) -> list[str]:
    """Check targets; the CLI supplies its Git index inventory for portability."""
    errors = []
    root = root.resolve()
    if symlink_in_path(path, root):
        return ["documentation source must not be a symlink"]
    for target in link_targets(path.read_text(encoding="utf-8")):
        target = re.sub(r"\\([\\()\[\] ])", r"\1", target)
        try:
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            name = unquote(url.path)
            candidate = (root / name.lstrip("/")) if name.startswith("/") else (path.parent / name)
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                errors.append(f"link escapes the repository: {target}")
            elif symlink_in_path(candidate, root):
                errors.append(f"local target must not use a symlink: {target}")
            elif not resolved.exists():
                errors.append(f"missing local target: {target}")
            elif tracked_paths is not None:
                present = resolved in tracked_paths
                if resolved.is_dir():
                    present = any(item.is_relative_to(resolved) for item in tracked_paths)
                if not present:
                    errors.append(f"local target is not Git-tracked: {target}")
        except ValueError as exc:
            errors.append(f"invalid local target {target!r}: {exc}")
    return errors


def check_svg(path: Path) -> list[str]:
    if path.is_symlink():
        return ["SVG source must not be a symlink"]
    text = path.read_text(encoding="utf-8")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.I):
        return ["SVG must not declare a DTD or entity"]
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"invalid SVG XML: {exc}"]
    errors = []
    if root.tag != SVG + "svg":
        errors.append("expected an SVG root and namespace")
    for tag in ("title", "desc"):
        child = root.find(SVG + tag)
        if child is None or not "".join(child.itertext()).strip():
            errors.append(f"SVG needs a nonempty {tag}")
    try:
        box = [float(v) for v in root.get("viewBox", "").replace(",", " ").split()]
        if len(box) != 4 or not all(math.isfinite(v) for v in box) or not (box[2] > 0 and box[3] > 0):
            raise ValueError
    except ValueError:
        errors.append("SVG needs a valid viewBox with positive dimensions")
    ids = [el.get("id") for el in root.iter() if el.get("id")]
    if len(ids) != len(set(ids)):
        errors.append("SVG has duplicate IDs")
    for ref in root.get("aria-labelledby", "").split():
        if ref not in ids:
            errors.append(f"missing aria-labelledby target: {ref}")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in {"script", "foreignobject", "style", "set"} or tag.startswith("animate"):
            errors.append(f"unexpected active/styled SVG element: {tag}")
        for key, value in element.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if name.startswith("on") or name == "style":
                errors.append(f"unexpected SVG attribute: {name}")
            if name in {"href", "src"} and value:
                if not value.startswith("#"):
                    errors.append(f"SVG resource must be internal: {value}")
                elif value[1:] not in ids:
                    errors.append(f"missing SVG definition: {value}")
            for ref in re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", value, re.I):
                ref = ref.strip()
                if not ref.startswith("#"):
                    errors.append(f"SVG resource must be internal: {ref}")
                elif ref[1:] not in ids:
                    errors.append(f"missing SVG definition: {ref}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Cannot list tracked files: {exc}", file=sys.stderr)
        return 2
    paths = [root / name for name in output.decode("utf-8").split("\0") if name]
    tracked_paths = frozenset(paths)
    checked = 0
    failed = False
    for path in paths:
        if path.suffix.lower() not in {".md", ".svg"}:
            continue
        checked += 1
        try:
            errors = check_markdown(path, root, tracked_paths) if path.suffix.lower() == ".md" else check_svg(path)
        except (OSError, UnicodeError) as exc:
            errors = [str(exc)]
        for error in errors:
            print(f"{path.relative_to(root)}: {error}", file=sys.stderr)
            failed = True
    if not checked:
        print("No tracked Markdown or SVG files found", file=sys.stderr)
        return 2
    print(f"Checked {checked} Markdown/SVG files; {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
