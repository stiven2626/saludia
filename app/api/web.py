"""Vistas web (capa de presentación) para cada rol del sistema."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.domain.models import ItemFormula, Rol
from app.services.clinica import ReglaNegocioError

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

INICIO_POR_ROL = {Rol.PACIENTE: "/paciente", Rol.MEDICO: "/medico",
                  Rol.FARMACEUTICO: "/farmacia", Rol.ADMINISTRADOR: "/admin"}


def _c(request: Request):
    return request.app.state.contenedor


def _usuario(request: Request):
    uid = request.cookies.get("uid")
    return _c(request).db.usuarios.obtener(int(uid)) if uid and uid.isdigit() else None


def _ir(url: str, msg: str = "", err: str = "") -> RedirectResponse:
    if msg:
        url += f"?msg={quote(msg)}"
    elif err:
        url += f"?err={quote(err)}"
    return RedirectResponse(url, status_code=303)


def _render(request: Request, plantilla: str, **ctx) -> HTMLResponse:
    ctx.update(usuario=_usuario(request), msg=request.query_params.get("msg"),
               err=request.query_params.get("err"), app_nombre=_c(request).settings.app_nombre)
    return templates.TemplateResponse(request, plantilla, ctx)


def _exigir(request: Request, rol: Rol):
    u = _usuario(request)
    return u if u and u.rol == rol else None


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return _render(request, "login.html", usuarios=_c(request).db.usuarios.listar())


@router.post("/ingresar")
def ingresar(request: Request, usuario_id: int = Form(...)):
    u = _c(request).db.usuarios.obtener(usuario_id)
    if u is None:
        return _ir("/", err="Usuario no válido")
    resp = _ir(INICIO_POR_ROL[u.rol])
    resp.set_cookie("uid", str(u.id), httponly=True, samesite="lax")
    return resp


@router.get("/salir")
def salir():
    resp = _ir("/")
    resp.delete_cookie("uid")
    return resp


# ---------- Paciente ----------
@router.get("/paciente", response_class=HTMLResponse)
def vista_paciente(request: Request):
    u = _exigir(request, Rol.PACIENTE)
    if not u:
        return _ir("/", err="Ingrese como paciente")
    c = _c(request)
    medicos = {m.id: m for m in c.db.medicos()}
    opciones = [(m, f) for m in medicos.values() for f in c.citas.franjas_disponibles(m.id)]
    formulas = [f for f in c.db.formulas.listar() if f.paciente_id == u.id]
    triaje = c.db.triajes[-1] if request.query_params.get("triaje") and c.db.triajes else None
    return _render(request, "paciente.html", citas=c.citas.de_paciente(u.id), medicos=medicos,
                   opciones=opciones, formulas=formulas, meds={m.id: m for m in c.db.medicamentos.listar()},
                   triaje=triaje)


@router.post("/paciente/citas")
def paciente_solicitar(request: Request, opcion: str = Form(...), motivo: str = Form("")):
    u = _exigir(request, Rol.PACIENTE)
    if not u:
        return _ir("/")
    medico_id, fecha = opcion.split("|", 1)
    try:
        _c(request).citas.solicitar(u.id, int(medico_id), fecha, motivo)
    except ReglaNegocioError as e:
        return _ir("/paciente", err=str(e))
    return _ir("/paciente", msg=f"Cita programada para {fecha}")


@router.post("/paciente/citas/{cita_id}/cancelar")
def paciente_cancelar(request: Request, cita_id: int):
    u = _exigir(request, Rol.PACIENTE)
    if not u:
        return _ir("/")
    try:
        _c(request).citas.cancelar(cita_id, u.id)
    except ReglaNegocioError as e:
        return _ir("/paciente", err=str(e))
    return _ir("/paciente", msg="Cita cancelada")


@router.post("/paciente/asistente")
def paciente_asistente(request: Request, sintomas: str = Form("")):
    if not _exigir(request, Rol.PACIENTE):
        return _ir("/")
    c = _c(request)
    try:
        c.db.triajes.append(c.asistente.orientar(sintomas))
    except ValueError as e:
        return _ir("/paciente", err=str(e))
    return RedirectResponse("/paciente?triaje=1#asistente", status_code=303)


# ---------- Médico ----------
@router.get("/medico", response_class=HTMLResponse)
def vista_medico(request: Request):
    u = _exigir(request, Rol.MEDICO)
    if not u:
        return _ir("/", err="Ingrese como médico")
    c = _c(request)
    return _render(request, "medico.html", agenda=c.citas.agenda_medico(u.id),
                   pacientes={p.id: p for p in c.db.pacientes()}, medicamentos=c.db.medicamentos.listar())


@router.post("/medico/citas/{cita_id}/atender")
def medico_atender(request: Request, cita_id: int, descripcion: str = Form(""), codigo_cie10: str = Form(""),
                   medicamento_id: str = Form(""), cantidad: int = Form(0), indicaciones: str = Form("")):
    u = _exigir(request, Rol.MEDICO)
    if not u:
        return _ir("/")
    items = [ItemFormula(int(medicamento_id), cantidad, indicaciones)] if medicamento_id else []
    try:
        _, formula = _c(request).atencion.registrar(cita_id, u.id, descripcion, codigo_cie10, items)
    except ReglaNegocioError as e:
        return _ir("/medico", err=str(e))
    extra = f" y fórmula #{formula.id} enviada a farmacia" if formula else ""
    return _ir("/medico", msg=f"Diagnóstico registrado{extra}")


# ---------- Farmacia ----------
@router.get("/farmacia", response_class=HTMLResponse)
def vista_farmacia(request: Request):
    if not _exigir(request, Rol.FARMACEUTICO):
        return _ir("/", err="Ingrese como farmacéutico")
    c = _c(request)
    return _render(request, "farmacia.html", pendientes=c.farmacia.pendientes(),
                   meds={m.id: m for m in c.db.medicamentos.listar()},
                   pacientes={p.id: p for p in c.db.pacientes()}, alertas=c.farmacia.alertas_stock(),
                   stock_minimo=c.settings.stock_minimo)


@router.post("/farmacia/formulas/{formula_id}/dispensar")
def farmacia_dispensar(request: Request, formula_id: int):
    if not _exigir(request, Rol.FARMACEUTICO):
        return _ir("/")
    try:
        _c(request).farmacia.dispensar(formula_id)
    except ReglaNegocioError as e:
        return _ir("/farmacia", err=str(e))
    return _ir("/farmacia", msg=f"Fórmula #{formula_id} dispensada")


# ---------- Administrador ----------
@router.get("/admin", response_class=HTMLResponse)
def vista_admin(request: Request):
    if not _exigir(request, Rol.ADMINISTRADOR):
        return _ir("/", err="Ingrese como administrador")
    c = _c(request)
    return _render(request, "admin.html", ind=c.tablero.indicadores(), circuito=c.asistente.breaker,
                   motor=c.asistente.principal.nombre, alertas=c.farmacia.alertas_stock(),
                   entorno=c.settings.entorno)
