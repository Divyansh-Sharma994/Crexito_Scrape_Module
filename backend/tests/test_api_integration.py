import pytest
from main import health
from routers.articles import get_articles
from db.database import init_db

@pytest.mark.asyncio
async def test_health_check():
    await init_db()
    response = await health()
    assert response["status"] in ["healthy", "degraded"]
    assert "total_articles" in response

@pytest.mark.asyncio
async def test_articles_fetch():
    await init_db()
    response = await get_articles(page_size=2)
    assert response["page_size"] == 2
    assert "articles" in response
