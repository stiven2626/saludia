"""Servicios de negocio: citas, atención médica y farmacia.

Cada servicio tiene una sola responsabilidad (alta cohesión) y solo conoce los
repositorios, no la interfaz web ni el almacenamiento (bajo acoplamiento).
"""
from __future__ import annotations

from collections import Counter

from app.domain.models import (
    Cita, Diagnostico, EstadoCita, EstadoFormula, Formula, ItemFormula, Medico,
)
from app.repositories.memory import UnidadDeDatos


class ReglaNegocioError(ValueError):
    """Error cuando una operación viola una regla del negocio."""


class CitaService:
    def __init__(self, db: UnidadDeDatos) -> None:
        self.db = db

    def franjas_disponibles(self, medico_id: int) -> list[str]:
        medico = self._medico(medico_id)
        ocupadas = {c.fecha_hora for c in self.db.citas.listar()
                    if c.medico_id == medico_id and c.estado == EstadoCita.PROGRAMADA}
        return [f for f in medico.franjas if f not in ocupadas]

    def solicitar(self, paciente_id: int, medico_id: int, fecha_hora: str, motivo: str) -> Cita:
        if not any(p.id == paciente_id for p in self.db.pacientes()):
            raise ReglaNegocioError("El paciente no existe.")
        if fecha_hora not in self.franjas_disponibles(medico_id):
            raise ReglaNegocioError("La franja seleccionada no está disponible.")
        if any(c.paciente_id == paciente_id and c.fecha_hora == fecha_hora
               and c.estado == EstadoCita.PROGRAMADA for c in self.db.citas.listar()):
            raise ReglaNegocioError("Ya tiene una cita programada a esa hora.")
        cita = Cita(self.db.citas.siguiente_id(), paciente_id, medico_id, fecha_hora,
                    motivo.strip() or "Consulta general")
        return self.db.citas.agregar(cita)

    def cancelar(self, cita_id: int, paciente_id: int) -> Cita:
        cita = self._cita(cita_id)
        if cita.paciente_id != paciente_id:
            raise ReglaNegocioError("Solo el paciente titular puede cancelar la cita.")
        if cita.estado != EstadoCita.PROGRAMADA:
            raise ReglaNegocioError("Solo se pueden cancelar citas programadas.")
        cita.estado = EstadoCita.CANCELADA
        return cita

    def de_paciente(self, paciente_id: int) -> list[Cita]:
        return sorted((c for c in self.db.citas.listar() if c.paciente_id == paciente_id),
                      key=lambda c: c.fecha_hora)

    def agenda_medico(self, medico_id: int) -> list[Cita]:
        return sorted((c for c in self.db.citas.listar() if c.medico_id == medico_id),
                      key=lambda c: c.fecha_hora)

    def _medico(self, medico_id: int) -> Medico:
        medico = self.db.usuarios.obtener(medico_id)
        if not isinstance(medico, Medico):
            raise ReglaNegocioError("El médico no existe.")
        return medico

    def _cita(self, cita_id: int) -> Cita:
        cita = self.db.citas.obtener(cita_id)
        if cita is None:
            raise ReglaNegocioError("La cita no existe.")
        return cita


class AtencionService:
    """El diagnóstico solo existe si hay una cita programada (regla del caso de estudio)."""

    def __init__(self, db: UnidadDeDatos) -> None:
        self.db = db

    def registrar(self, cita_id: int, medico_id: int, descripcion: str, codigo_cie10: str,
                  items: list[ItemFormula]) -> tuple[Diagnostico, Formula | None]:
        cita = self.db.citas.obtener(cita_id)
        if cita is None or cita.medico_id != medico_id:
            raise ReglaNegocioError("La cita no existe o no pertenece a este médico.")
        if cita.estado != EstadoCita.PROGRAMADA:
            raise ReglaNegocioError("Solo se puede diagnosticar una cita programada.")
        if not descripcion.strip():
            raise ReglaNegocioError("El diagnóstico es obligatorio.")
        for item in items:
            if self.db.medicamentos.obtener(item.medicamento_id) is None:
                raise ReglaNegocioError("Medicamento no encontrado.")
            if item.cantidad <= 0:
                raise ReglaNegocioError("La cantidad debe ser mayor que cero.")
        diag = self.db.diagnosticos.agregar(Diagnostico(
            self.db.diagnosticos.siguiente_id(), cita.id, descripcion.strip(),
            codigo_cie10.strip().upper() or "Z00.0"))
        formula = None
        if items:
            formula = self.db.formulas.agregar(Formula(
                self.db.formulas.siguiente_id(), diag.id, cita.paciente_id, items))
        cita.estado = EstadoCita.ATENDIDA
        return diag, formula


class FarmaciaService:
    def __init__(self, db: UnidadDeDatos, stock_minimo: int) -> None:
        self.db = db
        self.stock_minimo = stock_minimo

    def pendientes(self) -> list[Formula]:
        return [f for f in self.db.formulas.listar() if f.estado == EstadoFormula.PENDIENTE]

    def dispensar(self, formula_id: int) -> Formula:
        formula = self.db.formulas.obtener(formula_id)
        if formula is None:
            raise ReglaNegocioError("La fórmula no existe.")
        if formula.estado != EstadoFormula.PENDIENTE:
            raise ReglaNegocioError("La fórmula ya fue dispensada.")
        for item in formula.items:
            med = self.db.medicamentos.obtener(item.medicamento_id)
            if med is None or med.stock < item.cantidad:
                nombre = med.nombre if med else "desconocido"
                raise ReglaNegocioError(f"Stock insuficiente de {nombre}.")
        for item in formula.items:
            self.db.medicamentos.obtener(item.medicamento_id).stock -= item.cantidad  # type: ignore[union-attr]
        formula.estado = EstadoFormula.DISPENSADA
        return formula

    def alertas_stock(self):
        return [m for m in self.db.medicamentos.listar() if m.stock < self.stock_minimo]


class TableroService:
    def __init__(self, db: UnidadDeDatos) -> None:
        self.db = db

    def indicadores(self) -> dict:
        citas = Counter(c.estado.value for c in self.db.citas.listar())
        triajes = Counter(t.nivel.value for t in self.db.triajes)
        formulas = Counter(f.estado.value for f in self.db.formulas.listar())
        return {
            "pacientes": len(self.db.pacientes()),
            "medicos": len(self.db.medicos()),
            "citas": dict(citas),
            "citas_total": sum(citas.values()),
            "triajes": dict(triajes),
            "triajes_total": len(self.db.triajes),
            "formulas": dict(formulas),
        }
