"""Asistente de IA para orientación (triaje) de síntomas.

Patrón Strategy: el motor que analiza los síntomas es intercambiable.
- MotorReglas: motor local basado en reglas clínicas simples (siempre disponible).
- MotorExterno: delega en un proveedor de IA en la nube vía HTTP.

El servicio envuelve el motor principal con un Circuit Breaker y usa el motor
de reglas como respaldo, de modo que el asistente nunca deja de responder.

Aviso: el asistente orienta, no diagnostica. El diagnóstico lo registra el médico.
"""
from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod

import httpx

from app.config import Settings
from app.domain.models import NivelUrgencia, ResultadoTriaje
from app.resilience.circuit_breaker import CircuitBreaker

AVISO = ("Esta orientación no reemplaza la valoración médica. "
         "Ante una emergencia llame a la línea 123.")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


class MotorTriaje(ABC):
    nombre = "abstracto"

    @abstractmethod
    def analizar(self, sintomas: str) -> ResultadoTriaje: ...


class MotorReglas(MotorTriaje):
    nombre = "reglas"

    # (palabras clave, nivel, especialidad, recomendación) — ordenadas de mayor a menor gravedad
    REGLAS = [
        (["dolor de pecho", "dificultad para respirar", "no puedo respirar", "desmayo",
          "convulsion", "sangrado abundante", "perdida de conciencia"],
         NivelUrgencia.ALTA, "Urgencias",
         "Acuda de inmediato al servicio de urgencias más cercano o llame a la línea 123."),
        (["nino", "bebe", "hijo", "hija", "menor de edad"],
         NivelUrgencia.MEDIA, "Pediatría",
         "Solicite una cita con Pediatría. Si hay fiebre mayor a 39 °C, acuda a urgencias."),
        (["fiebre", "tos", "gripa", "dolor de garganta", "diarrea", "vomito", "dolor de cabeza"],
         NivelUrgencia.MEDIA, "Medicina general",
         "Solicite una cita con Medicina general en las próximas 24 a 48 horas. Hidrátese bien."),
        (["piel", "brote", "mancha", "acne", "picazon", "rasquina", "alergia en la piel"],
         NivelUrgencia.BAJA, "Dermatología",
         "Solicite una cita con Dermatología. Evite automedicarse con cremas."),
        (["ansiedad", "estres", "tristeza", "insomnio", "no duermo"],
         NivelUrgencia.MEDIA, "Psicología",
         "Solicite una cita de orientación psicológica. No está solo: busque apoyo."),
    ]

    def analizar(self, sintomas: str) -> ResultadoTriaje:
        texto = _normalizar(sintomas)
        for claves, nivel, especialidad, recomendacion in self.REGLAS:
            if any(clave in texto for clave in claves):
                return ResultadoTriaje(sintomas, nivel, especialidad,
                                       f"{recomendacion} {AVISO}", self.nombre)
        return ResultadoTriaje(sintomas, NivelUrgencia.BAJA, "Medicina general",
                               f"Solicite una cita con Medicina general para valoración. {AVISO}",
                               self.nombre)


class MotorExterno(MotorTriaje):
    """Cliente de un proveedor de IA externo (por ejemplo, un modelo de lenguaje en la nube)."""

    nombre = "externo"

    def __init__(self, url: str, timeout: float, simular_falla: bool = False) -> None:
        self.url = url
        self.timeout = timeout
        self.simular_falla = simular_falla

    def analizar(self, sintomas: str) -> ResultadoTriaje:
        if self.simular_falla or not self.url:
            raise ConnectionError("Proveedor de IA no disponible")
        respuesta = httpx.post(self.url, json={"sintomas": sintomas}, timeout=self.timeout)
        respuesta.raise_for_status()
        datos = respuesta.json()
        return ResultadoTriaje(sintomas, NivelUrgencia(datos["nivel"]), datos["especialidad"],
                               f"{datos['recomendacion']} {AVISO}", self.nombre)


class AsistenteService:
    def __init__(self, principal: MotorTriaje, respaldo: MotorTriaje, breaker: CircuitBreaker) -> None:
        self.principal = principal
        self.respaldo = respaldo
        self.breaker = breaker

    def orientar(self, sintomas: str) -> ResultadoTriaje:
        if not sintomas.strip():
            raise ValueError("Describa sus síntomas.")

        def usar_respaldo() -> ResultadoTriaje:
            resultado = self.respaldo.analizar(sintomas)
            if self.principal is not self.respaldo:
                resultado.motor = f"{self.respaldo.nombre} (respaldo)"
            return resultado

        return self.breaker.llamar(lambda: self.principal.analizar(sintomas), usar_respaldo)


def crear_asistente(settings: Settings) -> AsistenteService:
    reglas = MotorReglas()
    breaker = CircuitBreaker(settings.cb_umbral_fallas, settings.cb_tiempo_recuperacion)
    if settings.ia_proveedor_url or settings.simular_falla_ia:
        principal: MotorTriaje = MotorExterno(settings.ia_proveedor_url, settings.ia_timeout_segundos,
                                              settings.simular_falla_ia)
    else:
        principal = reglas
    return AsistenteService(principal, reglas, breaker)
