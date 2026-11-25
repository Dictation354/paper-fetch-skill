"""Historical receipt ordering, validation, and project scope."""

import json
import os
from hashlib import sha256
from pathlib import Path

import pytest

from paper_fetch.delivery.lookup import lookup_receipt, lookup_receipts
from paper_fetch.models import (
    TRUNCATION_WARNING,
    ArticleModel,
    Metadata,
    Reference,
    RenderOptions,
    Section,
)
from paper_fetch.workflow.rendering import build_fetch_envelope
from tests.golden_criteria import golden_criteria_scenario_asset

DOI = "10.1000/example"


def test_lookup_selects_newest_public_fingerprinted_sidecar(tmp_path):
    payload = {
        "doi": DOI.upper(),
        "source": "wiley_browser",
        "markdown": "# Full text",
        "has_fulltext": True,
        "content_kind": "fulltext",
        "warnings": [],
        "quality": {"has_fulltext": True, "content_kind": "fulltext", "warnings": []},
    }

    def write(hex_digit, timestamp, **overrides):
        fingerprint = hex_digit * 64
        path = tmp_path / f"10.1000_example.{fingerprint}.fetch-envelope.json"
        path.write_text(
            json.dumps(
                {"version": 8, "request_fingerprint": fingerprint, "payload": payload}
                | overrides
            ),
            encoding="utf-8",
        )
        os.utime(path, (timestamp, timestamp))
        return path

    write("a", 1)
    expected = write("b", 2, credential_scope="public", capability_scope="public")
    write("c", 3, capability_scope="private")
    write("d", 4, credential_scope="private")
    write("e", 5, request_fingerprint="f" * 64)
    write("f", 6, payload={**payload, "warnings": [TRUNCATION_WARNING]})
    write("A", 7)
    assert lookup_receipt(DOI, [tmp_path]) is None
    assert lookup_receipt(DOI, [tmp_path], include_legacy=True) == {
        "schema_version": 1,
        "contract": "paper-fetch/legacy-lookup",
        "status": "found",
        "doi": DOI,
        "source": "wiley_browser",
        "sidecar_path": str(expected),
        "sidecar_version": 8,
        "body_json_pointer": "/payload/markdown",
        "acceptance": "historical_unverified",
    }


def test_lookup_legacy_manifest_then_markdown_rejects_symlinks(tmp_path):
    root = tmp_path / "project"
    run = root / ".paper-fetch-results" / "run"
    manifest = run / "paper" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    local = manifest.with_name("accepted.md")
    local.write_text("# Full text", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text(f"---\ndoi: {DOI}\n---\n# Outside", encoding="utf-8")
    body_link = manifest.with_name("body.md")
    body_link.symlink_to(outside)
    data = {
        "schema_version": 2,
        "doi": DOI,
        "target": "paper",
        "content_kind": "fulltext",
        "source": "wiley_browser",
        "completed_at": "2025-01-01T10:00:00+00:00",
    }
    manifest.write_text(
        json.dumps({**data, "output_paths": {"markdown": "accepted.md"}}),
        encoding="utf-8",
    )
    newer = run / "newer" / "manifest.json"
    newer.parent.mkdir()
    newer.write_text(
        json.dumps({**data, "body_path": str(outside), "completed_at": "2026-01-01"}),
        encoding="utf-8",
    )
    md = root / "retained.md"
    md.write_text(
        f'---\ndoi: "{DOI.upper()}"\nsource: archive\nhas_fulltext: TrUe\n---\n# Article\n\nBody text.\n',
        encoding="utf-8",
    )
    (root / "linked.md").symlink_to(outside)
    bad = root / "bad.md"
    bad.write_text(f"---\ndoi: {DOI}\ntruncated: true\n---\n# Body", encoding="utf-8")
    os.utime(bad, (2_000_000_000, 2_000_000_000))

    assert lookup_receipt(DOI, [root]) is None
    found = lookup_receipt(DOI, [root], include_legacy=True)
    assert found["body_path"] == str(local)
    assert found["manifest_path"] == str(manifest)
    local.unlink()
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert lookup_receipt(DOI, [root], include_legacy=True)["body_path"] == str(md)
    md.unlink()
    assert lookup_receipt(DOI, [root], include_legacy=True) is None


@pytest.mark.parametrize(
    ("fields", "body", "accepted"),
    [
        ("", "# Personal notes", False),
        ("content_kind: abstract_only\n", "Abstract", False),
        ("has_fulltext: true\ncontent_kind: metadata_only\n", "# Body", False),
        ("has_fulltext: false\ncontent_kind: fulltext\n", "# Body", False),
        ("content_kind: fulltext\ntruncated: yes\n", "# Body", False),
        ("content_kind: fulltext\ntruncated: 1\n", "# Body", False),
        ("content_kind: fulltext\n", TRUNCATION_WARNING, False),
        ("has_fulltext: true\n", "  \n", False),
        ("has_fulltext: true\n", "# Article", False),
        ("has_fulltext: true\n", "# Article\n\n## Summary\n\nSummary text.", False),
        ("has_fulltext: true\n", "# Article\n\n## Abstract\n\nAbstract text.", False),
        ("has_fulltext: true\n", "# Article\n\n**Abstract.** Abstract text.", False),
        ("content_kind: FULLTEXT\n", "# Article\n\nBody text.", True),
    ],
)
def test_legacy_markdown_requires_untruncated_managed_fulltext(
    tmp_path, fields, body, accepted
):
    (tmp_path / "text.md").write_text(f"---\ndoi: {DOI}\n{fields}---\n{body}")
    assert (
        lookup_receipt(DOI, [tmp_path], include_legacy=True) is not None
    ) is accepted


@pytest.mark.parametrize(("max_tokens", "accepted"), [(80, False), ("full_text", True)])
def test_legacy_markdown_checks_actual_export_for_body_truncation(
    tmp_path, max_tokens, accepted
):
    article = ArticleModel(
        doi=DOI,
        source="elsevier_xml",
        metadata=Metadata(title="Example", abstract="A short abstract."),
        sections=[
            Section(
                heading="Methods", level=2, kind="body", text="Samples were measured."
            ),
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="The measurements confirmed a consistent effect. " * 25,
            ),
        ],
        references=[Reference(raw="Writer, A. A related study. Journal, 2026.")],
    )
    envelope = build_fetch_envelope(
        article,
        modes={"markdown"},
        render=RenderOptions(max_tokens=max_tokens, include_refs="none"),
    )
    markdown = envelope.markdown
    assert markdown is not None
    assert "has_fulltext: true" in markdown
    assert f"token_estimate: {article.quality.token_estimate}" in markdown
    assert "Samples were measured." in markdown
    assert TRUNCATION_WARNING not in markdown
    assert "## References" not in markdown
    assert ("## Results" in markdown) is accepted

    export = tmp_path / "export.md"
    export.write_text(markdown, encoding="utf-8")
    receipt = lookup_receipt(DOI, [tmp_path], include_legacy=True)
    if accepted:
        assert receipt["status"] == "found"
        assert receipt["body_path"] == str(export)
    else:
        assert receipt is None


@pytest.mark.parametrize(
    ("version", "scopes", "markdown", "accepted"),
    [
        (8, {}, "Article", False),
        (8, {"credential_scope": None, "capability_scope": None}, "Article", False),
        (8, {"capability_scope": "public"}, "Article", True),
        (
            8,
            {"capability_scope": "public", "credential_scope": "private"},
            "Article",
            False,
        ),
        (8, {"credential_scope": "public"}, TRUNCATION_WARNING, False),
        (2, {"credential_scope": None}, "Article", False),
        (2, {"credential_scope": "public"}, "Article", True),
        (2, {"capability_scope": "restricted"}, "Article", False),
        (2, {}, TRUNCATION_WARNING, False),
    ],
)
def test_legacy_sidecar_scope_and_body_are_checked(
    tmp_path, version, scopes, markdown, accepted
):
    facts = {"has_fulltext": True, "content_kind": "fulltext", "warnings": []}
    data = {
        "version": version,
        "payload": {
            **facts,
            "quality": facts,
            "markdown": markdown,
            "doi": DOI,
            "source": "archive",
        },
        **scopes,
    }
    stem = "10.1000_example"
    if version == 8:
        data["request_fingerprint"] = "a" * 64
        stem += "." + data["request_fingerprint"]
    (tmp_path / f"{stem}.fetch-envelope.json").write_text(json.dumps(data))
    assert (
        lookup_receipt(DOI, [tmp_path], include_legacy=True) is not None
    ) is accepted


@pytest.mark.parametrize("historical_hash_names", [True, False])
def test_legacy_v2_nested_acceptance_and_artifact_verification(
    tmp_path, historical_hash_names
):
    manifest = tmp_path / ".paper-fetch-results/run/paper/manifest.json"
    manifest.parent.mkdir(parents=True)
    markdown = manifest.with_name("original.md")
    body = b"# Fulltext"
    markdown.write_bytes(body)
    artifact = {
        "path": "original.md",
        "kind": "markdown",
        "verification_status": "verified",
        "size": len(body),
        "sha256": sha256(body).hexdigest(),
    }
    if not historical_hash_names:
        artifact["role"] = "reading_markdown"
        del artifact["kind"]
        artifact["expected_size"] = artifact.pop("size")
        artifact["expected_sha256"] = artifact.pop("sha256")
    data = {
        "schema_version": 2,
        "source": "wiley_browser",
        "acceptance": {
            "target": "paper",
            "identity": {"doi": DOI.upper()},
            "overall": "degraded",
            "content": {"has_fulltext": True},
        },
        "output_artifacts": [artifact],
    }

    def lookup():
        manifest.write_text(json.dumps(data))
        return lookup_receipt(DOI, [tmp_path], include_legacy=True)

    assert lookup()["body_path"] == str(markdown)
    markdown.write_bytes(b"!" + body[1:])
    assert lookup() is None
    markdown.write_bytes(body)
    data["acceptance"]["content"]["has_fulltext"] = False
    assert lookup() is None
    del data["acceptance"]
    data.update(
        doi=DOI,
        body_path=markdown.name,
        has_fulltext=True,
        content_kind="abstract_only",
    )
    assert lookup() is None
    data.update(has_fulltext=False, content_kind="fulltext")
    assert lookup() is None
    del data["has_fulltext"]
    markdown.write_text(TRUNCATION_WARNING)
    assert lookup() is None


def test_legacy_v2_reads_verified_v7_7_2_reading_markdown(tmp_path):
    manifest = tmp_path / ".paper-fetch-results/run/paper/manifest.json"
    manifest.parent.mkdir(parents=True)
    markdown = manifest.with_name("body.md")
    body = b"# Article\n\nBody text.\n"
    markdown.write_bytes(body)
    # Serialized with the v7.7.2 manifest writer. Rebase its absolute body path.
    data = json.loads(
        golden_criteria_scenario_asset(
            "legacy_lookup_v7_7_2", "manifest.json"
        ).read_text(encoding="utf-8")
    )
    data["output_artifacts"][0]["path"] = str(markdown)
    manifest.write_text(json.dumps(data), encoding="utf-8")

    receipt = lookup_receipt(DOI, [tmp_path], include_legacy=True)
    assert receipt["body_path"] == str(markdown)
    markdown.write_bytes(body.replace(b"Body", b"Edit"))
    assert lookup_receipt(DOI, [tmp_path], include_legacy=True) is None


def test_batch_scans_each_input_directory_once(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    for name in ("example", "second"):
        (project / f"{name}.md").write_text(
            f"---\ndoi: 10.1000/{name}\ncontent_kind: fulltext\n---\n# Article\n\nBody text."
        )
    original_glob = Path.glob
    scans = []

    def glob(path, pattern, **kwargs):
        scans.append((path, pattern))
        return original_glob(path, pattern, **kwargs)

    monkeypatch.setattr(Path, "glob", glob)
    second = "10.1000/second"
    assert set(
        lookup_receipts([DOI, second, DOI], [project, project], include_legacy=True)
    ) == {DOI, second}
    assert scans == [
        (project / ".paper-fetch-results", "*/*/manifest.json"),
        (project, "*.fetch-envelope.json"),
        (project, "*.md"),
    ]


def test_legacy_v3_does_not_treat_non_sibling_sections_symlink_as_missing(tmp_path):
    from paper_fetch.manifest import ManifestOutputArtifactSpec, build_manifest_record
    from tests.support.fetch_fixtures import sample_envelope

    path = tmp_path / ".paper-fetch-results/run/paper/manifest.json"
    envelope = sample_envelope(modes={"article", "markdown"}, doi=DOI)
    path.parent.mkdir(parents=True)
    body = path.with_name("body.md")
    body.write_text(envelope.markdown, encoding="utf-8")
    section_index = path.with_name("sections.json")
    section_index.write_text("{}", encoding="utf-8")
    specs = [
        ManifestOutputArtifactSpec(path=str(body), kind="reading_markdown"),
        ManifestOutputArtifactSpec(path=str(section_index), kind="section_index"),
    ]
    record = build_manifest_record(
        query=DOI,
        index=1,
        attempt=1,
        tool_version="8.0.0",
        request_parameters={},
        asset_profile="none",
        output_artifacts=specs,
        envelope=envelope,
    ).model_dump(mode="json")
    sections = next(
        item for item in record["output_artifacts"] if item["kind"] == "section_index"
    )
    Path(sections["path"]).unlink()
    sections["path"] = "indexes/retained-sections.json"
    path.write_text(json.dumps(record))
    assert (
        lookup_receipt(DOI, [tmp_path], include_legacy=True)["contract"]
        == "paper-fetch/legacy-lookup"
    )

    for directory in (tmp_path, path.parent):
        link = directory / sections["path"]
        link.parent.mkdir()
        link.symlink_to(tmp_path / "missing.json")
        assert lookup_receipt(DOI, [tmp_path], include_legacy=True) is None
        link.unlink()
