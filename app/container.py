"""Composición de dependencias: aquí se decide qué implementación usa cada servicio."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.repositories.memory import UnidadDeDatos, datos_semilla
from app.services.asistente import AsistenteService, crear_asistente
from app.services.clinica import AtencionService, CitaService, FarmaciaService, TableroService


@dataclass
class Contenedor:
    settings: Settings
    db: UnidadDeDatos
    citas: CitaService
    atencion: AtencionService
    farmacia: FarmaciaService
    tablero: TableroService
    asistente: AsistenteService


def crear_contenedor(settings: Settings | None = None) -> Contenedor:
    settings = settings or get_settings()
    db = datos_semilla()
    return Contenedor(
        settings=settings,
        db=db,
        citas=CitaService(db),
        atencion=AtencionService(db),
        farmacia=FarmaciaService(db, settings.stock_minimo),
        tablero=TableroService(db),
        asistente=crear_asistente(settings),
    )
