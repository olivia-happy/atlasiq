import os
from pathlib import Path


TEST_DATABASE_PATH = Path(__file__).resolve().parent.parent / "atlasiq-test.db"

if TEST_DATABASE_PATH.exists():
    TEST_DATABASE_PATH.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./atlasiq-test.db"
