from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://parserly:parserly@localhost:5432/parserly_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "parserly-test-secret")


@pytest.fixture
def runtime_dir() -> Iterator[Path]:
    root = Path(__file__).resolve().parents[1] / "test_runtime"
    path = root / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)

    try:
        yield path
    finally:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
        if resolved_root in resolved_path.parents:
            shutil.rmtree(resolved_path, ignore_errors=True)
