import os
import tempfile

TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["ELEPHANT_DB_PATH"] = TEST_DB
os.environ["ELEPHANT_ADMIN_KEY"] = "test-admin"

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client():
    try: os.unlink(TEST_DB)
    except FileNotFoundError: pass
    with TestClient(app) as test_client:
        yield test_client

