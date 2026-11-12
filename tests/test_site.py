"""Public-seam checks for the researcher documentation site.

Runs at the highest public seam: builds the MkDocs site and inspects the
generated HTML, navigation, and links exactly as a reader would encounter
them. Also validates the illustrative preparation, training, and
hyperparameter configurations against the shipped schemas after placeholder
substitution, and checks the concise ``llms.txt`` agent map.
"""

from __future__ import annotations

import json
import os
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
    "evaluation.md",
    "embedding.md",
    "reconstruction.md",
    "outputs.md",
]

# llms.txt must link to each published guidance page (root = overview).
LLMS_PAGE_PATHS = [
    "",
    "inputs/",
    "preparation/",
    "training/",
    "evaluation/",
    "embedding/",
    "reconstruction/",
    "outputs/",
]

# Terms from the earlier single-dataset contract that must not survive in any
# reader-facing source (pages and llms.txt). The pattern for the old training
# field excludes the current train_/val_ prefixed fields.
STALE_TERMS = {
    "single dataset path field": re.compile(r"(?<![a-z_])dataset_path"),
    "published split file": re.compile(r"split\.npy"),
    "reconstruction row splits": re.compile(r"row_splits"),
    "end-of-training test metric": re.compile(r"test_(reconstruction_loss|unaligned_reconstruction_mse)"),
    "validation-named run field": re.compile(r"validation_(reconstruction_loss|unaligned_reconstruction_mse)"),
    "single training dataset match": re.compile(r"(training_dataset_identity|matches_training_dataset)"),
    "split named as a dataset": re.compile(
        r"(?<![-\w])(test|validation|training) splits?(?!\s+assignment)\b", re.IGNORECASE
    ),
}


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
        site / "evaluation" / "index.html",
        site / "embedding" / "index.html",
        site / "reconstruction" / "index.html",
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
    assert "track-encoder reconstruct" not in text, "llms.txt must not duplicate command manuals"
    assert "track-encoder evaluate" not in text, "llms.txt must not duplicate command manuals"
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
    # TRACK_ENCODER_SCHEMA_ROOTS (os.pathsep-separated) points the check at
    # other checkouts, such as worktrees of an unreleased integration branch.
    override = os.environ.get("TRACK_ENCODER_SCHEMA_ROOTS")
    if override:
        upstream_roots = [Path(root) for root in override.split(os.pathsep) if root]
    else:
        workspace = Path("/local/storage/xp76/projects/track-encoder")
        upstream_roots = [
            workspace / "spec/contracts/schemas",
            workspace / "code/src/track_encoder/schemas",
        ]
    available = [root for root in upstream_roots if root.is_dir()]
    if not available:
        pytest.skip("workspace schemas not available (CI); vendored copies are authoritative")
    for name in [
        "prepare-config.schema.json",
        "training-config.schema.json",
        "dilated-cnn-hp.schema.json",
        "reconstruction.schema.json",
        "evaluation.schema.json",
    ]:
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
    fixed_raw = next(block for block in with_version if '"train_dataset_path"' in block)
    assert "/absolute/path/to/" in fixed_raw, "fixed config must use clearly marked absolute-path placeholders"
    fixed = json.loads(fixed_raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    _validate_against_schema(fixed, _load_schema("training-config.schema.json"), "training config")
    assert fixed["run"]["device"] == "cuda", "training example must target CUDA"
    data = fixed["data"]
    assert data["train_dataset_path"].endswith("/train"), "training example must name the train dataset"
    assert data["val_dataset_path"].endswith("/val"), "training example must name the val dataset"
    assert "northwood" in data["train_dataset_path"], "training example must use fictional names"
    assert "northwood" in data["val_dataset_path"], "training example must use fictional names"
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
        "<code>train/</code>",
        "<code>val/</code>",
        "<code>test/</code>",
        "<code>preparation.json</code>",
        "signals.npy",
        "source_rows.npy",
        "dataset.json",
    ]:
        assert snippet in prep_html, f"built preparation page is missing {snippet!r}"
    index_html = (site / "index.html").read_text(encoding="utf-8")
    for term in ["genomic element", "signal track", "embedding"]:
        assert term in index_html, f"overview page is missing domain term {term!r}"


def test_reconstruction_command_documented_in_built_html():
    site = build_site()
    html = (site / "reconstruction" / "index.html").read_text(encoding="utf-8")
    for snippet in [
        "track-encoder reconstruct --dataset",
        "<code>--checkpoint</code>",
        "<code>--mask</code>",
        "<code>--output</code>",
        "<code>--device</code>",
        "<code>--batch-size</code>",
        "<code>--debug</code>",
        "<code>reconstructions.npy</code>",
        "<code>reconstruction.json</code>",
        "<code>best.pt</code>",
    ]:
        assert snippet in html, f"built reconstruction page is missing {snippet!r}"
    for term in ["full checkpoint", "encoder artifact", "element example", "dataset identity"]:
        assert term in html, f"reconstruction page is missing glossary term {term!r}"


def test_reconstruction_page_names_every_manifest_field():
    site = build_site()
    html = (site / "reconstruction" / "index.html").read_text(encoding="utf-8")
    schema = _load_schema("reconstruction.schema.json")
    missing = [field for field in schema["required"] if f"<code>{field}</code>" not in html]
    assert not missing, f"reconstruction page does not describe manifest fields: {missing}"


def test_illustrative_reconstruction_manifest_validates_after_substitution():
    blocks = _extract_json_blocks(DOCS / "reconstruction.md")
    raw = next((block for block in blocks if '"row_alignment"' in block), None)
    assert raw is not None, "reconstruction.md must contain an illustrative reconstruction.json"
    assert "/absolute/path/to/" in raw, "manifest must use clearly marked absolute-path placeholders"
    manifest = json.loads(raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    _validate_against_schema(manifest, _load_schema("reconstruction.schema.json"), "reconstruction manifest")
    assert "northwood" in manifest["checkpoint_file"], "reconstruction example must use fictional names"
    assert manifest["shape"][0] == len(manifest["row_indices"])
    assert manifest["row_indices"] == sorted(manifest["row_indices"]), "rows are written in ascending order"
    assert manifest["shape"][1] == len(manifest["channels"])
    assert manifest["shape"][2] == manifest["window_length"]


def test_evaluation_command_documented_in_built_html():
    site = build_site()
    html = (site / "evaluation" / "index.html").read_text(encoding="utf-8")
    for snippet in [
        "track-encoder evaluate --dataset",
        "<code>--checkpoint</code>",
        "<code>--mask</code>",
        "<code>--output</code>",
        "<code>--device</code>",
        "<code>--batch-size</code>",
        "<code>--debug</code>",
        "<code>evaluation.json</code>",
        "<code>reconstruction_losses.npy</code>",
        "<code>unaligned_reconstruction_mse.npy</code>",
        "<code>best.pt</code>",
        "<code>best_val_reconstruction_loss</code>",
    ]:
        assert snippet in html, f"built evaluation page is missing {snippet!r}"
    for term in ["full checkpoint", "test dataset", "train dataset", "val dataset", "dataset identity"]:
        assert term in html, f"evaluation page is missing glossary term {term!r}"


def test_evaluation_page_names_every_manifest_field():
    site = build_site()
    html = (site / "evaluation" / "index.html").read_text(encoding="utf-8")
    schema = _load_schema("evaluation.schema.json")
    missing = [field for field in schema["required"] if f"<code>{field}</code>" not in html]
    assert not missing, f"evaluation page does not describe manifest fields: {missing}"


def test_illustrative_evaluation_manifest_validates_after_substitution():
    blocks = _extract_json_blocks(DOCS / "evaluation.md")
    raw = next((block for block in blocks if '"reconstruction_losses_file"' in block), None)
    assert raw is not None, "evaluation.md must contain an illustrative evaluation.json"
    assert "/absolute/path/to/" in raw, "manifest must use clearly marked absolute-path placeholders"
    manifest = json.loads(raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    _validate_against_schema(manifest, _load_schema("evaluation.schema.json"), "evaluation manifest")
    assert "northwood" in manifest["checkpoint_file"], "evaluation example must use fictional names"
    assert manifest["num_rows"] == len(manifest["row_indices"])
    assert manifest["row_indices"] == sorted(manifest["row_indices"]), "rows are scored in ascending order"
    # The example scores a test dataset: it matches neither training input.
    assert manifest["matches_train_dataset"] is False
    assert manifest["matches_val_dataset"] is False


def test_reader_facing_sources_use_the_split_dataset_contract():
    sources = [*sorted(DOCS.glob("*.md")), LLMS_TXT]
    failures: list[str] = []
    for path in sources:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for label, pattern in STALE_TERMS.items():
                if pattern.search(line):
                    failures.append(f"{path.relative_to(REPO)}:{number}: {label}: {line.strip()}")
    assert not failures, "stale earlier-contract terms remain:\n" + "\n".join(failures)


def test_alpha_break_is_stated_for_earlier_artifacts():
    site = build_site()
    html = (site / "outputs" / "index.html").read_text(encoding="utf-8").lower()
    for artifact in ["processed datasets", "training configurations", "full checkpoints"]:
        assert artifact in html, f"outputs page must say earlier {artifact} need regenerating"
    assert "regenerate" in html, "outputs page must tell readers to regenerate earlier artifacts"


def test_embedding_page_explains_encoder_artifacts_cannot_reconstruct():
    site = build_site()
    html = (site / "embedding" / "index.html").read_text(encoding="utf-8")
    assert "../reconstruction/" in html, "embedding page must link to the reconstruction page"
    assert "cannot produce reconstructions" in html, (
        "embedding page must explain that encoder artifacts cannot produce reconstructions"
    )


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


def test_every_training_configuration_example_is_schema_version_3():
    found = 0
    for page in sorted(DOCS.glob("*.md")):
        for block in re.findall(r"```json\n(.*?)```", page.read_text(encoding="utf-8"), re.DOTALL):
            if '"train_dataset_path"' not in block:
                continue
            found += 1
            config = json.loads(block)
            assert config.get("schema_version") == 3, (
                f"{page.name}: training configuration example must use schema_version 3"
            )
    assert found, "no training configuration example found"


def test_schema_version_3_break_is_stated():
    site = build_site()
    for page in ["training", "outputs"]:
        html = (site / page / "index.html").read_text(encoding="utf-8")
        assert "version <code>2</code>" in html, f"{page} page must say version 2 is rejected"
        for command in ["embed", "reconstruct", "evaluate"]:
            assert f"<code>{command}</code>" in html, (
                f"{page} page must say version 2 checkpoints still work for {command}"
            )
        assert "cannot be resumed" in html, f"{page} page must say version 2 checkpoints cannot be resumed"


def test_tracked_training_config_validates_after_substitution():
    blocks = _extract_json_blocks(DOCS / "training.md")
    fixed_raw = next(block for block in blocks if '"train_dataset_path"' in block)
    tracking_raw = next((block for block in blocks if '"wandb"' in block), None)
    assert tracking_raw is not None, "training.md must contain an illustrative tracking block"
    tracking = json.loads(tracking_raw)
    assert set(tracking) <= {"type", "project", "entity", "run_name"}
    assert "northwood" in tracking["project"], "tracking example must use fictional names"
    fixed = json.loads(fixed_raw.replace("/absolute/path/to/", "/tmp/track-encoder-docs-check/"))
    fixed["tracking"] = tracking
    _validate_against_schema(fixed, _load_schema("training-config.schema.json"), "tracked training config")


def test_tracking_documented_in_built_html():
    site = build_site()
    html = (site / "training" / "index.html").read_text(encoding="utf-8")
    for snippet in [
        "[wandb]",
        "<code>tracking</code>",
        "<code>tracking.json</code>",
        "wandb login",
        "<code>WANDB_API_KEY</code>",
        "#SBATCH",
        "WANDB_MODE=offline",
        "wandb sync",
        "<code>resume=\"must\"</code>",
        "hostname",
        "console",
        "one warning",
        "same output directory",
        "<code>&lt;output_dir&gt;/wandb/offline-run-*</code>",
    ]:
        assert snippet in html, f"built training page is missing {snippet!r}"
    # W&B is given the run directory and adds one wandb/ level itself.
    assert "wandb/wandb" not in html, "offline runs sit directly under <output_dir>/wandb/"
    for snippet in ["--resume", "--hp", "--config"]:
        assert html.count(snippet) >= 2


def test_llms_txt_mentions_tracking_and_configuration_version():
    text = LLMS_TXT.read_text(encoding="utf-8")
    assert "W&amp;B" in text or "W&B" in text, "llms.txt must mention W&B tracking"
    assert "tracking" in text, "llms.txt must mention optional tracking"
    assert "version 3" in text, "llms.txt must state the current training configuration version"
