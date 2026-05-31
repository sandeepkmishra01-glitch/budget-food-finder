from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import search, health, cuisines


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Budget Food Finder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "https://*.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(search.router, prefix="/api")
app.include_router(cuisines.router, prefix="/api")
