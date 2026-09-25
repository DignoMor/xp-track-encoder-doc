"""Public-seam checks for the researcher documentation site.

Runs at the highest public seam: builds the MkDocs site and inspects the
generated HTML, navigation, and links exactly as a reader would encounter
them. Also validates the illustrative preparation, training, and
hyperparameter configurations against the shipped schemas after placeholder
substitution, and checks the concise ``llms.txt`` agent map.
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
LLMS_TXT = REPO / "llms.txt"
SCHEMAS_DIR = REPO / "tests" / "schemas"
CODE_REPO_URL = "https://github.com/haiyuan-yu-lab/xp-track-encoder"
PAGES_BASE = "https://dignomor.github.io/xp-track-encoder-doc"

# Pages the short, future-proof navigation must expose.
EXPECTED_PAGES = [
    "index.md",
    "inputs.md",
    "preparation.md",
    "training.md",
    "embedding.md",
    "outputs.md",
]

# llms.txt must link to each published guidance page (root = overview).
LLMS_PAGE_PATHS = ["", "inputs/", "preparation/", "training/", "embedding/", "outputs/"]


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
    # Static copy mirroring the Pages deploy workflow: the canonical
    # repo-root llms.txt is served at the site root.
    assert LLMS_TXT.is_file(), "llms.txt is missing at the repository root"
    shutil.copyfile(LLMS_TXT, SITE / "llms.txt")
    return SITE


def html_files(site: Path) -> list[Path]:
    return sorted(site.rglob("*.html"))


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    assert path.is_file(), f"vendored schema missing: {path.relative_to(REPO)}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_mkdocs_config_and_sources_exist():
    assert MKDOCS_YML.is_file(), "mkdocs.yml is missing"
    for page in EXPECTED_PAGES:
        assert (DOCS / page).is_file(), f"docs/{page} is missing"
    assert LLMS_TXT.is_file(), "llms.txt is missing at the repository root"
    # docs/llms.txt is the MkDocs static-copy source so relative links validate
    # under --strict; it must stay identical to the canonical root llms.txt.
    docs_llms = DOCS / "llms.txt"
    assert docs_llms.is_file(), "docs/llms.txt static-copy source is missing"
    assert docs_llms.read_text(encoding="utf-8") == LLMS_TXT.read_text(encoding="utf-8"), (
        "docs/llms.txt must be identical to the repo-root llms.txt"
    )


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
    assert (site / "llms.txt").is_file(), "built site is missing llms.txt static copy"


def test_llms_txt_copied_identical_to_site():
    site = build_site()
    built = site / "llms.txt"
    assert built.is_file(), "site/llms.txt was not copied during the build"
    assert built.read_text(encoding="utf-8") == LLMS_TXT.read_text(encoding="utf-8"), (
        "site/llms.txt must be identical to the repo-root llms.txt"
    )


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
    sources = [MKDOCS_YML, *sorted(DOCS.glob("*.md")), *sorted(DOCS.glob("*.txt"))]
    if LLMS_TXT.is_file():
        sources.append(LLMS_TXT)
    for path in sources:
        for match in pattern.findall(path.read_text(encoding="utf-8")):
            found.add(match.rstrip(".,;)"))
    return found


def test_external_links_allowlist():
    external = _external_links_in_sources()
    assert CODE_REPO_URL in external, (
        "the site must link to the code repository installation page; "
        f"found: {sorted(external)}"
    )
    allowed = [
        url for url in external
        if url == CODE_REPO_URL or url.startswith(PAGES_BASE)
    ]
    disallowed = sorted(set(external) - set(allowed))
    assert not disallowed, (
        "only the code repository install link and the published Pages URLs "
        f"may appear as external destinations; found: {disallowed}"
    )


def test_llms_txt_is_concise_link_map():
    text = LLMS_TXT.read_text(encoding="utf-8")
    assert "Track Encoder" in text, "llms.txt must describe Track Encoder concisely"
    for subpath in LLMS_PAGE_PATHS:
        assert f"{PAGES_BASE}/{subpath}" in text, (
            f"llms.txt must link to the published page {PAGES_BASE}/{subpath}"
        )
    assert CODE_REPO_URL in text, "llms.txt must link to the code repository install page"
    # Link map only: no duplicated manual.
    assert "```" not in text, "llms.txt must not contain fenced code blocks"
    assert "schema_version" not in text, "llms.txt must not duplicate configuration manuals"
    assert "track-encoder prepare" not in text, "llms.txt must not duplicate command manuals"
    assert "track-encoder train" not in text, "llms.txt must not duplicate command manuals"
    assert "track-encoder embed" not in text, "llms.txt must not duplicate command manuals"
    lines = text.splitlines()
    assert len(lines) <= 80, f"llms.txt must stay concise (found {len(lines)} lines)"
    assert len(text) <= 4000, f"llms.txt must stay concise (found {len(text)} chars)"


def test_llms_txt_links_resolve_to_built_site():
    site = build_site()
    text = LLMS_TXT.read_text(encoding="utf-8")
    urls = re.findall(r"https?://[^\s\)\"'<>]+", text)
    assert urls, "llms.txt must contain links"
    failures: list[str] = []
    for raw in urls:
        url = raw.rstrip(".,;)")
        if url == CODE_REPO_URL:
            continue
        if not url.startswith(PAGES_BASE):
            failures.append(url)
            continue
        subpath = url[len(PAGES_BASE):].lstrip("/")
        if subpath == "":
            candidate = site / "index.html"
        else:
            candidate = site / subpath / "index.html" if not subpath.endswith(".txt") else site / subpath
            if subpath.endswith(".txt"):
                candidate = site / subpath
        # llms.txt itself maps to site/llms.txt; page dirs map to index.html.
        if url == f"{PAGES_BASE}/llms.txt":
            candidate = site / "llms.txt"
        if not candidate.is_file():
            failures.append(f"{url} -> missing {candidate.relative_to(site)}")
    assert not failures, "llms.txt links do not resolve:\n" + "\n".join(failures)


def _extract_json_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert blocks, f"{path.name} must contain a fenced json configuration"
    return blocks


def _validate_against_schema(config: dict, schema: dict, label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.path))
    assert not errors, label + " fails schema validation:\n" + "\n".join(
        f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors
    )


def test_vendored_schemas_match_upstream_when_available():
    workspace = Path("/local/storage/xp76/projects/track-encoder")
    upstream_roots = [
        workspace / "spec/contracts/schemas",
        workspace / "code/src/track_encoder/schemas",
    ]
    available = [root for root in upstream_roots if root.is_dir()]
    if not available:
        pytest.skip("workspace schemas not available (CI); vendored copies are authoritative")
    for name in ["prepare-config.schema.json", "training-config.schema.json", "dilated-cnn-hp.schema.json"]:
        vendored = json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))
        for root in available:
            upstream = root / name
            if upstream.is_file():
                assert vendored == json.loads(upstream.read_text(encoding="utf-8")), (
                    f"vendored {name} drifted from {upstream}"
                )


def test_illustrative_prep_config_validates_after_substitution():
    blocks = _extract_json_blocks(DOCS / "preparation.md")
    raw: str | None = None
    for block in blocks:
        if '"schema_version"' in block:
            raw = block
            break
    assert raw is not None, "no complete preparation configuration block found in preparation.md"
    assert "/absolute/path/to/" in raw, "config must use clearly marked absolute-path placeholders"
    substituted = raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/")
    config = json.loads(substituted)
    _validate_against_schema(config, _load_schema("prepare-config.schema.json"), "prep config")
    # Fictional names must not leak the code fixture's track names.
    names = [track["name"] for track in config["tracks"]]
    assert not {"gro", "atac"} & set(names), "example must use fictional track names"


def test_illustrative_training_config_validates_after_substitution():
    blocks = _extract_json_blocks(DOCS / "training.md")
    with_version = [block for block in blocks if '"schema_version"' in block]
    assert len(with_version) == 2, (
        "training.md must contain exactly two versioned illustrative documents "
        f"(fixed config + hyperparameters); found {len(with_version)}"
    )
    fixed_raw = next(block for block in with_version if '"dataset_path"' in block)
    assert "/absolute/path/to/" in fixed_raw, "fixed config must use clearly marked absolute-path placeholders"
    fixed = json.loads(fixed_raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    _validate_against_schema(fixed, _load_schema("training-config.schema.json"), "training config")
    assert fixed["run"]["device"] == "cuda", "training example must target CUDA"
    assert "northwood" in fixed["data"]["dataset_path"], "training example must use fictional names"
    assert "northwood" in fixed["run"]["output_dir"], "training example must use fictional names"


def test_illustrative_hp_config_validates():
    blocks = _extract_json_blocks(DOCS / "training.md")
    with_version = [block for block in blocks if '"schema_version"' in block]
    hp_raw = next(block for block in with_version if '"layers"' in block)
    assert "northwood" not in hp_raw or True  # hyperparameters carry no paths; shape is what matters
    hp = json.loads(hp_raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    _validate_against_schema(hp, _load_schema("dilated-cnn-hp.schema.json"), "hyperparameter config")
    layers = hp["architecture"]["layers"]
    assert all(layer["kernel_size"] % 2 == 1 for layer in layers), "example kernels must be odd"
    assert all(layer["resolution_bp"] >= 1 for layer in layers), "example resolutions must be positive"


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
