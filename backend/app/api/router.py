"""
Top-level API router.

Includes all sub-routers under /api/v1.
New route modules are registered here as they are implemented.
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# ── Sub-routers (added as each module is implemented) ────────────
# from app.api.health import router as health_router
# from app.api.companies import router as companies_router
# from app.api.documents import router as documents_router
# from app.api.chat import router as chat_router
# from app.api.analysis import router as analysis_router
# from app.api.financials import router as financials_router
# from app.api.tasks import router as tasks_router

# api_router.include_router(health_router)
# api_router.include_router(companies_router)
# api_router.include_router(documents_router)
# api_router.include_router(chat_router)
# api_router.include_router(analysis_router)
# api_router.include_router(financials_router)
# api_router.include_router(tasks_router)
