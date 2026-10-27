"""Patrón Circuit Breaker (cortacircuitos).

Protege al sistema cuando un servicio externo (por ejemplo, un proveedor de IA
en la nube) falla de forma repetida. En lugar de seguir esperando respuestas
que no llegan, el circuito se "abre" y se usa una respuesta de respaldo.

Estados:
- CERRADO: las llamadas pasan normalmente.
- ABIERTO: las llamadas no se intentan; se usa el respaldo.
- SEMIABIERTO: pasado el tiempo de recuperación se permite una llamada de prueba.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Callable, TypeVar

R = TypeVar("R")


class EstadoCircuito(str, Enum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    SEMIABIERTO = "semiabierto"


class CircuitBreaker:
    def __init__(self, umbral_fallas: int = 3, tiempo_recuperacion: float = 30.0,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.umbral_fallas = umbral_fallas
        self.tiempo_recuperacion = tiempo_recuperacion
        self._reloj = reloj
        self.fallas = 0
        self._abierto_desde: float | None = None
        self._estado = EstadoCircuito.CERRADO

    @property
    def estado(self) -> EstadoCircuito:
        if (self._estado == EstadoCircuito.ABIERTO and self._abierto_desde is not None
                and self._reloj() - self._abierto_desde >= self.tiempo_recuperacion):
            self._estado = EstadoCircuito.SEMIABIERTO
        return self._estado

    def llamar(self, operacion: Callable[[], R], respaldo: Callable[[], R]) -> R:
        if self.estado == EstadoCircuito.ABIERTO:
            return respaldo()
        try:
            resultado = operacion()
        except Exception:
            self._registrar_falla()
            return respaldo()
        self._reiniciar()
        return resultado

    def _registrar_falla(self) -> None:
        self.fallas += 1
        if self._estado == EstadoCircuito.SEMIABIERTO or self.fallas >= self.umbral_fallas:
            self._estado = EstadoCircuito.ABIERTO
            self._abierto_desde = self._reloj()

    def _reiniciar(self) -> None:
        self.fallas = 0
        self._abierto_desde = None
        self._estado = EstadoCircuito.CERRADO
