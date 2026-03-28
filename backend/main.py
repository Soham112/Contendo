import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from memory.feedback_store import init_db
from memory.hierarchy_store import init_db as init_hierarchy_db
from routers import generate, history, ideas, ingest, library, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_hierarchy_db()
    yield


app = FastAPI(title="Contendo API", lifespan=lifespan)

# CORS: always allow localhost dev origins; add FRONTEND_ORIGIN in production.
_cors_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "https://*.vercel.app",
]
_frontend_origin = os.environ.get("FRONTEND_ORIGIN", "").strip()
if _frontend_origin and _frontend_origin not in _cors_origins:
    _cors_origins.append(_frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(generate.router)
app.include_router(history.router)
app.include_router(library.router)
app.include_router(ideas.router)
app.include_router(stats.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
