import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models.user  # noqa: F401 — registers User/ExamSet with Base.metadata
from app.api.auth_routes import router as auth_router
from app.api.exam_routes import router as exam_router
from app.api.routes import router
from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import setup_logging
from app.models.question import Base

setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    yield


app = FastAPI(title="English Inspector API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(router)
app.include_router(auth_router)
app.include_router(exam_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
