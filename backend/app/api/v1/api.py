from fastapi import APIRouter

from app.api.v1.routers import analysis, auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(analysis.router)
api_router.include_router(auth.router)
