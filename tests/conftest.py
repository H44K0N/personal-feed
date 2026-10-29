import os
import tempfile

# app.config reads these at import time, so set them before anything imports app.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="feed-test-")
os.environ["RUN_FETCHER"] = "0"
os.environ.pop("GEMINI_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main, models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


@pytest.fixture
def db():
    session = SessionLocal()
    for table in reversed(models.Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    # Not used as a context manager, so the lifespan (the fetch loop) doesn't run.
    return TestClient(main.app)
