import pytest

from rag.frontmatter import content_hash, metadata_for_ingest, parse_research_md, parse_version


def test_parse_research_md_with_frontmatter():
    text = """---
title: Test Doc
summary: Covers YB and CRV.
topics: [YB, CRV]
---
# Body title

Content here.
"""
    meta, body = parse_research_md(text)
    assert meta["title"] == "Test Doc"
    assert meta["summary"] == "Covers YB and CRV."
    assert meta["topics"] == ["YB", "CRV"]
    assert body.startswith("# Body title")
    assert "---" not in body.split("\n")[0]


def test_parse_research_md_without_frontmatter():
    text = "# Just body\n\nHello."
    meta, body = parse_research_md(text)
    assert meta == {}
    assert body == text


def test_content_hash_stable():
    h1 = content_hash("same body")
    h2 = content_hash("same body")
    h3 = content_hash("other")
    assert h1 == h2
    assert h1 != h3


def test_metadata_for_ingest_fallback_title():
    fields = metadata_for_ingest({}, fallback_title="My File")
    assert fields["title"] == "My File"
    assert fields["summary"] is None
    assert fields["topics"] is None
    assert fields["version"] == 1


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, 1),  # absent → default
        (2, 2),
        (5, 5),
        ("3", 3),  # string digits coerced
        (" 4 ", 4),
        (0, 1),  # below 1 → clamped
        (-7, 1),
        ("abc", 1),  # non-numeric → default
        (True, 1),  # bool is int subclass but must not count as version 1+
        (2.9, 1),  # float not accepted
    ],
)
def test_parse_version(raw, expected):
    assert parse_version(raw) == expected


def test_metadata_for_ingest_reads_version():
    fields = metadata_for_ingest({"summary": "s", "version": 3}, fallback_title="X")
    assert fields["version"] == 3
