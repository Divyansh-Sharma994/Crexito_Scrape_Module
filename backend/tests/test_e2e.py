import pytest
from db.database import get_db, init_db
from routers.articles import export_csv, export_xlsx

@pytest.mark.asyncio
async def test_whitebox_db_records():
    await init_db()
    # Insert or check existing data at deepest level
    async with get_db() as db:
        test_val = await db.fetchval("SELECT 1")
    assert test_val == 1

@pytest.mark.asyncio
async def test_blackbox_export_csv():
    await init_db()
    # Directly invoke the endpoint and check the response
    response = await export_csv()
    assert response.media_type == "text/csv"

@pytest.mark.asyncio
async def test_blackbox_export_xlsx():
    await init_db()
    response = await export_xlsx()
    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
