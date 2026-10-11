"""Offline input, output, denominator and local-page verification."""

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.has_main = False
        self.has_language = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script":
            raise ValueError("Static page must have no scripts")
        if tag == "html":
            self.has_language = values.get("lang") == "en"
        if tag == "main":
            self.has_main = True
        for key in ("href", "src"):
            value = values.get(key)
            if value:
                self.links.append(value)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path.cwd()
    manifest = json.loads((root / "data/manifest.json").read_text())
    for source in manifest["files"]:
        path = root / source["path"]
        assert sha(path) == source["sha256"]
        assert path.stat().st_size == source["bytes"]
    checksum_lines = (root / "outputs/SHA256SUMS").read_text().splitlines()
    for line in checksum_lines:
        expected, relative = line.split("  ", 1)
        assert sha(root / relative) == expected, relative
    evaluation = json.loads((root / "outputs/evaluation.json").read_text())
    assert evaluation["records"] == manifest["files"][1]["records"]
    for fold in json.loads((root / "outputs/split-evidence.json").read_text()):
        assert fold["profile_overlap"] == 0
    for point in json.loads((root / "outputs/frontier.json").read_text()):
        assert point["register_records"] == evaluation["records"]
        assert point["spend_cad"] <= point["budget_cad"]
        assert point["spend_cad"] == 6000 * point["refurbishments"] + 12000 * point["replacements"]
        assert point["fixed_plan_interval"][0] <= point["fixed_plan_interval"][1]
    provenance = json.loads((root / "outputs/provenance.json").read_text())
    assert sha(root / "config/study.json") == provenance["study_protocol_sha256"]
    assert sha(root / "outputs/splits.csv") == provenance["split_sha256"]
    site = root / "docs/site/index.html"
    page = Page()
    page.feed(site.read_text())
    assert page.has_main and page.has_language
    for link in page.links:
        if not link.startswith(("https:", "#")):
            assert (site.parent / link).is_file(), link
    note = PdfReader(root / "docs/TECHNICAL_NOTE.pdf")
    assert 4 <= len(note.pages) <= 6
    for index, page_pdf in enumerate(note.pages):
        assert f"Page {index + 1}:" in page_pdf.extract_text()
    for path in [root / "README.md", root / "DATA.md", *root.glob("docs/**/*.md"), site]:
        assert "\u2014" not in path.read_text(), path
    print(
        f"Verified {len(checksum_lines)} output hashes, frozen input hashes, complete denominators, local links and {len(note.pages)} technical-note pages"
    )


if __name__ == "__main__":
    main()
