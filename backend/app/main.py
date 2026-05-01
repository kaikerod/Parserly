from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.core.database import init_development_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_development_database()
    yield


app = FastAPI(title="Parserly ATS Resume Analyzer API", lifespan=lifespan)
app.include_router(api_router)
