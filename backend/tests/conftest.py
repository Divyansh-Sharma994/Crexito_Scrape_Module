import os
import pytest
import asyncio
from db.database import init_db

# Patch the environment BEFORE importing the app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

import pytest_asyncio

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # Setup the in-memory database with tables
    await init_db()
    yield
