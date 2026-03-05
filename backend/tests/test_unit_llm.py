import pytest
import asyncio
from scraper.llm import get_domain_name, get_ollama_model

# 1. Unit Testing: test get_domain_name
def test_get_domain_name():
    assert get_domain_name("https://www.nytimes.com/article/123") == "Nytimes"
    assert get_domain_name("http://techcrunch.com/funding") == "Techcrunch"
    assert get_domain_name("https://news.ycombinator.com") == "Ycombinator"
    assert get_domain_name("invalid_url") == ""
    assert get_domain_name("https://www.reuters.com") == "Reuters"

# 2. Integration / Unit (LLM Model detection)
@pytest.mark.asyncio
async def test_get_ollama_model():
    model = await get_ollama_model()
    # It should fallback to qwen2.5:3b or return a detected model string
    assert isinstance(model, str)
    assert len(model) > 0

