"""API REST versionada (/api/v1).

Es el punto de entrada único para clientes externos (app móvil, otras IPS,
un API Gateway en la nube). La documentación interactiva queda en /docs (Swagger).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.models import ItemFormula
from app.services.clinica import ReglaNegocioError

router = APIRouter(prefix="/api/v1", tags=["API v1"])


class SolicitudCita(BaseModel):
    paciente_id: int
    medico_id: int
    fecha_hora: str = Field(examples=["2026-11-03 08:00"])
    motivo: str = "Consulta general"


class SolicitudTriaje(BaseModel):
    sintomas: str = Field(examples=["Tengo fiebre y tos desde hace dos días"])


class ItemEntrada(BaseModel):
    medicamento_id: int
    cantidad: int
    indicaciones: str = ""


class SolicitudAtencion(BaseModel):
    medico_id: int
    descripcion: str
    codigo_cie10: str = ""
    items: list[ItemEntrada] = []


def _c(request: Request):
    return request.app.state.contenedor


def _error(e: ReglaNegocioError):
    raise HTTPException(status_code=422, detail=str(e))


@router.get("/medicos")
def listar_medicos(request: Request):
    c = _c(request)
    return [{"id": m.id, "nombre": m.nombre, "especialidad": m.especialidad,
             "franjas_disponibles": c.citas.franjas_disponibles(m.id)} for m in c.db.medicos()]


@router.post("/citas", status_code=201)
def crear_cita(datos: SolicitudCita, request: Request):
    try:
        cita = _c(request).citas.solicitar(datos.paciente_id, datos.medico_id, datos.fecha_hora, datos.motivo)
    except ReglaNegocioError as e:
        _error(e)
    return cita


@router.get("/pacientes/{paciente_id}/citas")
def citas_paciente(paciente_id: int, request: Request):
    return _c(request).citas.de_paciente(paciente_id)


@router.post("/citas/{cita_id}/atencion", status_code=201)
def atender(cita_id: int, datos: SolicitudAtencion, request: Request):
    items = [ItemFormula(i.medicamento_id, i.cantidad, i.indicaciones) for i in datos.items]
    try:
        diag, formula = _c(request).atencion.registrar(cita_id, datos.medico_id, datos.descripcion,
                                                       datos.codigo_cie10, items)
    except ReglaNegocioError as e:
        _error(e)
    return {"diagnostico": diag, "formula": formula}


@router.post("/asistente/triaje")
def triaje(datos: SolicitudTriaje, request: Request):
    c = _c(request)
    try:
        resultado = c.asistente.orientar(datos.sintomas)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    c.db.triajes.append(resultado)
    return resultado


@router.post("/formulas/{formula_id}/dispensar")
def dispensar(formula_id: int, request: Request):
    try:
        return _c(request).farmacia.dispensar(formula_id)
    except ReglaNegocioError as e:
        _error(e)


@router.get("/medicamentos")
def medicamentos(request: Request):
    return _c(request).db.medicamentos.listar()


@router.get("/indicadores")
def indicadores(request: Request):
    c = _c(request)
    datos = c.tablero.indicadores()
    datos["circuito_ia"] = c.asistente.breaker.estado.value
    return datos
