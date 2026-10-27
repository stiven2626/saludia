"""Configuración externa (patrón External Configuration Store).

Todos los parámetros que cambian entre entornos (local, pruebas, nube) se leen
de variables de entorno. Así el mismo artefacto se despliega en cualquier
entorno sin modificar el código.
"""
import os
from dataclasses import dataclass


def _bool(nombre: str, defecto: bool = False) -> bool:
    return os.getenv(nombre, str(defecto)).strip().lower() in {"1", "true", "si", "sí", "yes"}


@dataclass(frozen=True)
class Settings:
    app_nombre: str = os.getenv("APP_NOMBRE", "SaludIA")
    entorno: str = os.getenv("APP_ENTORNO", "local")
    # URL de un proveedor externo de IA (opcional). Si está vacía se usa el motor de reglas.
    ia_proveedor_url: str = os.getenv("IA_PROVEEDOR_URL", "")
    ia_timeout_segundos: float = float(os.getenv("IA_TIMEOUT_SEGUNDOS", "3"))
    # Permite demostrar el Circuit Breaker simulando que el proveedor externo falla.
    simular_falla_ia: bool = _bool("SIMULAR_FALLA_IA", False)
    cb_umbral_fallas: int = int(os.getenv("CB_UMBRAL_FALLAS", "3"))
    cb_tiempo_recuperacion: float = float(os.getenv("CB_TIEMPO_RECUPERACION", "30"))
    stock_minimo: int = int(os.getenv("STOCK_MINIMO", "10"))


def get_settings() -> Settings:
    return Settings()
