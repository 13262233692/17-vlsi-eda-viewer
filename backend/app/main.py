from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VLSI EDA Layout Viewer API",
        description="Chip layout visualization and analysis tool backend",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=86400,
    )

    app.include_router(api_router)

    @app.get("/")
    async def root():
        return {
            "name": "VLSI EDA Layout Viewer",
            "version": "0.1.0",
            "api": "/api",
            "docs": "/docs",
        }

    return app


app = create_app()
