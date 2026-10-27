"""Punto de entrada de SaludIA."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import rest, web
from app.config import Settings
from app.container import crear_contenedor

INICIO = datetime.now()


def crear_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="SaludIA API",
        description="Asistente inteligente para citas médicas, orientación de síntomas y dispensación de medicamentos.",
        version="1.0.0",
    )
    app.state.contenedor = crear_contenedor(settings)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    app.include_router(web.router)
    app.include_router(rest.router)

    @app.get("/health", tags=["Monitoreo"])
    def health():
        """Patrón Health Endpoint Monitoring: la nube consulta este endpoint para saber si la app vive."""
        c = app.state.contenedor
        return {
            "estado": "ok",
            "entorno": c.settings.entorno,
            "version": app.version,
            "activo_desde": INICIO.isoformat(timespec="seconds"),
            "circuito_ia": c.asistente.breaker.estado.value,
        }

    return app


app = crear_app()
