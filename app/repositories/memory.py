"""Patrón Repository.

Los servicios dependen de estas interfaces y no de cómo se guardan los datos.
El prototipo usa memoria; en producción bastaría con otra implementación
(PostgreSQL, Firestore, DynamoDB) sin tocar la lógica de negocio.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import count
from typing import Generic, TypeVar

from app.domain.models import (
    Cita, Diagnostico, Formula, Medicamento, Medico, Paciente, ResultadoTriaje, Rol, Usuario,
)

T = TypeVar("T")


class Repositorio(ABC, Generic[T]):
    @abstractmethod
    def agregar(self, entidad: T) -> T: ...

    @abstractmethod
    def obtener(self, id_: int) -> T | None: ...

    @abstractmethod
    def listar(self) -> list[T]: ...

    @abstractmethod
    def siguiente_id(self) -> int: ...


class RepositorioMemoria(Repositorio[T]):
    def __init__(self) -> None:
        self._datos: dict[int, T] = {}
        self._ids = count(1)

    def siguiente_id(self) -> int:
        return next(self._ids)

    def agregar(self, entidad: T) -> T:
        self._datos[entidad.id] = entidad  # type: ignore[attr-defined]
        return entidad

    def obtener(self, id_: int) -> T | None:
        return self._datos.get(id_)

    def listar(self) -> list[T]:
        return list(self._datos.values())


class UnidadDeDatos:
    """Agrupa los repositorios del sistema (un repositorio por agregado)."""

    def __init__(self) -> None:
        self.usuarios: RepositorioMemoria[Usuario] = RepositorioMemoria()
        self.citas: RepositorioMemoria[Cita] = RepositorioMemoria()
        self.diagnosticos: RepositorioMemoria[Diagnostico] = RepositorioMemoria()
        self.medicamentos: RepositorioMemoria[Medicamento] = RepositorioMemoria()
        self.formulas: RepositorioMemoria[Formula] = RepositorioMemoria()
        self.triajes: list[ResultadoTriaje] = []

    def pacientes(self) -> list[Paciente]:
        return [u for u in self.usuarios.listar() if isinstance(u, Paciente)]

    def medicos(self) -> list[Medico]:
        return [u for u in self.usuarios.listar() if isinstance(u, Medico)]


def datos_semilla() -> UnidadDeDatos:
    """Datos de demostración para el prototipo."""
    db = UnidadDeDatos()
    u = db.usuarios
    u.agregar(Paciente(u.siguiente_id(), "Laura Martínez", "1010101010", Rol.PACIENTE, "Nueva EPS"))
    u.agregar(Paciente(u.siguiente_id(), "Carlos Rojas", "2020202020", Rol.PACIENTE, "Sanitas"))
    u.agregar(Medico(u.siguiente_id(), "Dra. Ana Gómez", "3030303030", Rol.MEDICO, "Medicina general",
                     ["2026-11-03 08:00", "2026-11-03 08:30", "2026-11-03 09:00", "2026-11-04 10:00"]))
    u.agregar(Medico(u.siguiente_id(), "Dr. Jorge Díaz", "4040404040", Rol.MEDICO, "Pediatría",
                     ["2026-11-03 14:00", "2026-11-04 15:00"]))
    u.agregar(Medico(u.siguiente_id(), "Dra. Paula Ríos", "5050505050", Rol.MEDICO, "Dermatología",
                     ["2026-11-05 09:00", "2026-11-05 09:30"]))
    u.agregar(Usuario(u.siguiente_id(), "Andrés Peña (regente)", "6060606060", Rol.FARMACEUTICO))
    u.agregar(Usuario(u.siguiente_id(), "Administrador IPS", "7070707070", Rol.ADMINISTRADOR))

    m = db.medicamentos
    for nombre, pres, stock in [
        ("Acetaminofén 500 mg", "Tabletas x 10", 120),
        ("Ibuprofeno 400 mg", "Tabletas x 10", 60),
        ("Amoxicilina 500 mg", "Cápsulas x 21", 8),
        ("Loratadina 10 mg", "Tabletas x 10", 45),
        ("Sales de rehidratación oral", "Sobre", 30),
    ]:
        m.agregar(Medicamento(m.siguiente_id(), nombre, pres, stock))
    return db
