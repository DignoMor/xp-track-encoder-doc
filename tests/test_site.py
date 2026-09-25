"""Public-seam checks for the researcher documentation site.

Runs at the highest public seam: builds the MkDocs site and inspects the
generated HTML, navigation, and links exactly as a reader would encounter
them. Also validates the illustrative preparation configuration against the
shipped prepare-config schema after placeholder substitution.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
MKDOCS_YML = REPO / "mkdocs.yml"
SITE = REPO / "site"
SPEC_SCHEMA = (
    Path("/local/storage/xp76/projects/track-encoder")
    / "spec/contracts/schemas/prepare-config.schema.json"
)
CODE_REPO_URL = "https://github.com/haiyuan-yu-lab/xp-track-encoder"

# Pages the short, future-proof navigation must expose.
EXPECTED_PAGES = [
    "index.md",
    "inputs.md",
    "preparation.md",
    "training.md",
    "embedding.md",
    "outputs.md",
]


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []


    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value)


def build_site() -> Path:
    if SITE.exists():
        shutil.rmtree(SITE)
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"mkdocs build failed:\n{result.stdout}\n{result.stderr}"
    return SITE


def html_files(site: Path) -> list[Path]:
    return sorted(site.rglob("*.html"))


def test_mkdocs_config_and_sources_exist():
    assert MKDOCS_YML.is_file(), "mkdocs.yml is missing"
    for page in EXPECTED_PAGES:
        assert (DOCS / page).is_file(), f"docs/{page} is missing"


def test_build_produces_all_nav_pages():
    site = build_site()
    # use_directory_urls renders each page as <name>/index.html except the homepage.
    expected_html = [
        site / "index.html",
        site / "inputs" / "index.html",
        site / "preparation" / "index.html",
        site / "training" / "index.html",
        site / "embedding" / "index.html",
        site / "outputs" / "index.html",
    ]
    for page in expected_html:
        assert page.is_file(), f"built page missing: {page.relative_to(site)}"


def test_nav_lists_every_page_once():
    text = MKDOCS_YML.read_text(encoding="utf-8")
    for page in EXPECTED_PAGES:
        occurrences = text.count(page)
        assert occurrences == 1, f"nav must reference {page} exactly once (found {occurrences})"


def test_internal_links_resolve():
    site = build_site()
    failures: list[str] = []
    for html_file in html_files(site):
        collector = LinkCollector()
        collector.feed(html_file.read_text(encoding="utf-8"))
        for href in collector.links:
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if href.startswith(("data:", "javascript:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            if target.startswith("/"):
                # Root-absolute links resolve against the served site root.
                resolved = (site / target[1:]).resolve()
            else:
                resolved = (html_file.parent / target).resolve()
            # Directory links resolve to their index.html under use_directory_urls.
            candidates = [resolved, resolved / "index.html"]
            if resolved.suffix == "" and not any(c.is_file() for c in candidates):
                failures.append(f"{html_file.relative_to(site)} -> {href}")
            elif resolved.suffix != "" and not resolved.is_file():
                failures.append(f"{html_file.relative_to(site)} -> {href}")
    assert not failures, "broken internal links:\n" + "\n".join(failures)


def _external_links_in_sources() -> set[str]:
    pattern = re.compile(r"https?://[^\s\)\"'<>]+")
    found: set[str] = set()
    for path in [MKDOCS_YML, *sorted(DOCS.glob("*.md"))]:
        for match in pattern.findall(path.read_text(encoding="utf-8")):
            found.add(match.rstrip(".,;)"))
    return found


def test_single_external_link_points_to_code_repo():
    external = _external_links_in_sources()
    assert external == {CODE_REPO_URL}, (
        "the site must use exactly one external destination (the code "
        f"repository install link); found: {sorted(external)}"
    )


def _extract_prep_config_markdown() -> str:
    text = (DOCS / "preparation.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert blocks, "preparation.md must contain a fenced json preparation configuration"
    # The complete illustrative configuration is the one carrying schema_version.
    for block in blocks:
        if '"schema_version"' in block:
            return block
    raise AssertionError("no complete preparation configuration block found in preparation.md")


def test_illustrative_prep_config_validates_after_substitution():
    raw = _extract_prep_config_markdown()
    assert "/absolute/path/to/" in raw, "config must use clearly marked absolute-path placeholders"
    substituted = raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/")
    config = json.loads(substituted)
    schema = json.loads(SPEC_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.path))
    assert not errors, "prep config fails schema validation:\n" + "\n".join(
        f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors
    )
    # Fictional names must not leak the code fixture's track names.
    names = [track["name"] for track in config["tracks"]]
    assert not {"gro", "atac"} & set(names), "example must use fictional track names"


def test_cli_and_outputs_documented_in_built_html():
    site = build_site()
    prep_html = (site / "preparation" / "index.html").read_text(encoding="utf-8")
    for snippet in [
        "track-encoder prepare --config",
        "signals.npy",
        "split.npy",
        "dataset.json",
    ]:
        assert snippet in prep_html, f"built preparation page is missing {snippet!r}"
    index_html = (site / "index.html").read_text(encoding="utf-8")
    for term in ["genomic element", "signal track", "embedding"]:
        assert term in index_html, f"overview page is missing domain term {term!r}"


def test_no_bundled_input_data():
    banned = {".npy", ".bed", ".fa", ".fasta", ".bw", ".bigwig"}
    bundled = [
        path.relative_to(REPO).as_posix()
        for path in REPO.rglob("*")
        if path.is_file()
        and path.suffix.lower() in banned
        and "site" not in path.parts
        and ".git" not in path.parts
    ]
    assert not bundled, "docs must not bundle input data files:\n" + "\n".join(bundled)
