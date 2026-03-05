import pytest
from scraper.enrichment import decode_google_news_url, is_junk_body, clean_author_text, extract_author_from_html

# Unit - Google News Decryption
def test_decode_google_news_url():
    # We test an invalid format
    assert decode_google_news_url("https://www.nytimes.com") is None
    
    # We test a pseudo-encoded format (just a base64 encoded mock URL)
    import base64
    mock_url = "https://www.theverge.com/2026/fake-article"
    # Padding handling in target func ensures it decodes raw byte string
    encoded = base64.urlsafe_b64encode(mock_url.encode()).decode()
    test_str = f"https://news.google.com/rss/articles/{encoded}?hl=en-Us"
    assert decode_google_news_url(test_str) == mock_url

# Unit - Junk Filter
def test_is_junk_body():
    assert is_junk_body(None) is True
    assert is_junk_body("    ") is True
    assert is_junk_body("A") is True
    assert is_junk_body("This is a valid long article text which has more than five characters.") is False

# Unit - Author cleaning logic
def test_clean_author_text():
    assert clean_author_text(None) is None
    assert clean_author_text("{ function(e) }") is None
    assert clean_author_text("Admin") is None
    assert clean_author_text("John Doe") == "John Doe"

# Unit - HTML extraction author
def test_extract_author_from_html():
    html_1 = '<html><head><meta name="author" content="Jane Smith"></head><body></body></html>'
    html_2 = '<html><body><span class="author-name">Bob Journalism</span></body></html>'
    
    assert extract_author_from_html(html_1) == "Jane Smith"
    assert extract_author_from_html(html_2) == "Bob Journalism"
