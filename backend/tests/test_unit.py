import pytest
from scraper.enrichment import extract_author_from_html, extract_body_from_html, is_junk_body, decode_google_news_url
from scraper.engine import title_hash

@pytest.mark.unit
def test_title_hash_logic():
    t1 = "Apple cancels electric car project! "
    t2 = "apple cancels electric car project"
    assert title_hash(t1) == title_hash(t2)

@pytest.mark.unit
def test_is_junk_body():
    assert is_junk_body(None) is True
    assert is_junk_body("Short body.") is True
    assert is_junk_body("This is a sufficiently long body without any restricted keywords that might trigger the junk logic. " * 20) is False
    assert is_junk_body("Please enable javascript to view this wonderful " * 20) is True

@pytest.mark.unit
def test_author_extraction():
    html = """<html><body><script type="application/ld+json">{"@type": "NewsArticle", "author": {"@type":"Person", "name": "Tim Cook"}}</script></body></html>"""
    assert extract_author_from_html(html) == "Tim Cook"

@pytest.mark.unit
def test_decode_google_news():
    url = "https://news.google.com/rss/articles/CBMiRGh0dHBzOi8vd3d3LmNuYmMuY29tLzIwMjQvMDMvMDIvYXBwbGUtY2FuY2VscS1lbGVjdHJpYy1jYXItcHJvamVjdC5odG1s0gFIaHR0cHM6Ly93d3cuY25iYy5jb20vYW1wLzIwMjQvMDMvMDIvYXBwbGUtY2FuY2VscS1lbGVjdHJpYy1jYXItcHJvamVjdC5odG1s"
    assert "cnbc.com" in decode_google_news_url(url)
