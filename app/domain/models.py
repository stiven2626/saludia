"""Entidades del dominio de SaludIA."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Rol(str, Enum):
    PACIENTE = "paciente"
    MEDICO = "medico"
    FARMACEUTICO = "farmaceutico"
    ADMINISTRADOR = "administrador"


class EstadoCita(str, Enum):
    PROGRAMADA = "programada"
    ATENDIDA = "atendida"
    CANCELADA = "cancelada"


class NivelUrgencia(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class EstadoFormula(str, Enum):
    PENDIENTE = "pendiente"
    DISPENSADA = "dispensada"


@dataclass
class Usuario:
    id: int
    nombre: str
    documento: str
    rol: Rol


@dataclass
class Paciente(Usuario):
    eps: str = "Nueva EPS"


@dataclass
class Medico(Usuario):
    especialidad: str = "Medicina general"
    franjas: list[str] = field(default_factory=list)  # horarios disponibles "AAAA-MM-DD HH:MM"


@dataclass
class Cita:
    id: int
    paciente_id: int
    medico_id: int
    fecha_hora: str
    motivo: str
    estado: EstadoCita = EstadoCita.PROGRAMADA
    creada: datetime = field(default_factory=datetime.now)


@dataclass
class Diagnostico:
    id: int
    cita_id: int
    descripcion: str
    codigo_cie10: str
    fecha: datetime = field(default_factory=datetime.now)


@dataclass
class Medicamento:
    id: int
    nombre: str
    presentacion: str
    stock: int


@dataclass
class ItemFormula:
    medicamento_id: int
    cantidad: int
    indicaciones: str


@dataclass
class Formula:
    id: int
    diagnostico_id: int
    paciente_id: int
    items: list[ItemFormula]
    estado: EstadoFormula = EstadoFormula.PENDIENTE


@dataclass
class ResultadoTriaje:
    sintomas: str
    nivel: NivelUrgencia
    especialidad_sugerida: str
    recomendacion: str
    motor: str  # qué estrategia respondió (reglas, externo, respaldo)
    fecha: datetime = field(default_factory=datetime.now)
