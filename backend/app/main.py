from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models.user  # noqa: F401 — registers User/ExamSet with Base.metadata
from app.api.auth_routes import router as auth_router
from app.api.exam_routes import router as exam_router
from app.api.routes import router
from app.core.database import engine
from app.models.question import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="English Inspector API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(exam_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
