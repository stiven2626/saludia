from fastapi.testclient import TestClient

from app.config import Settings
from app.main import crear_app
from app.resilience.circuit_breaker import CircuitBreaker, EstadoCircuito


def cliente(**cfg) -> TestClient:
    return TestClient(crear_app(Settings(**cfg)))


def test_health():
    r = cliente().get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_flujo_completo_cita_diagnostico_dispensacion():
    c = cliente()
    r = c.post("/api/v1/citas", json={"paciente_id": 1, "medico_id": 3, "fecha_hora": "2026-11-03 08:00",
                                      "motivo": "Fiebre"})
    assert r.status_code == 201
    cita_id = r.json()["id"]

    # La misma franja ya no está disponible
    r = c.post("/api/v1/citas", json={"paciente_id": 2, "medico_id": 3, "fecha_hora": "2026-11-03 08:00"})
    assert r.status_code == 422

    r = c.post(f"/api/v1/citas/{cita_id}/atencion", json={
        "medico_id": 3, "descripcion": "Rinofaringitis aguda", "codigo_cie10": "J00",
        "items": [{"medicamento_id": 1, "cantidad": 2, "indicaciones": "1 cada 8 horas"}]})
    assert r.status_code == 201
    formula_id = r.json()["formula"]["id"]

    r = c.post(f"/api/v1/formulas/{formula_id}/dispensar")
    assert r.status_code == 200
    stock = {m["id"]: m["stock"] for m in c.get("/api/v1/medicamentos").json()}
    assert stock[1] == 118


def test_no_hay_diagnostico_sin_cita():
    r = cliente().post("/api/v1/citas/999/atencion", json={"medico_id": 3, "descripcion": "x"})
    assert r.status_code == 422


def test_triaje_por_reglas_detecta_urgencia():
    r = cliente().post("/api/v1/asistente/triaje", json={"sintomas": "Tengo dolor de pecho fuerte"})
    assert r.status_code == 200
    assert r.json()["nivel"] == "alta"
    assert r.json()["especialidad_sugerida"] == "Urgencias"


def test_circuit_breaker_usa_respaldo_y_se_abre():
    c = cliente(simular_falla_ia=True, cb_umbral_fallas=2)
    for _ in range(2):
        r = c.post("/api/v1/asistente/triaje", json={"sintomas": "fiebre y tos"})
        assert r.status_code == 200
        assert "respaldo" in r.json()["motor"]
    assert c.get("/health").json()["circuito_ia"] == "abierto"


def test_circuit_breaker_semiabierto_tras_recuperacion():
    t = [0.0]
    cb = CircuitBreaker(umbral_fallas=1, tiempo_recuperacion=10, reloj=lambda: t[0])

    def falla():
        raise RuntimeError

    cb.llamar(falla, lambda: None)
    assert cb.estado == EstadoCircuito.ABIERTO
    t[0] = 11
    assert cb.estado == EstadoCircuito.SEMIABIERTO
    cb.llamar(lambda: "ok", lambda: None)
    assert cb.estado == EstadoCircuito.CERRADO


def test_vistas_web_por_rol():
    c = cliente()
    assert c.get("/").status_code == 200
    for uid, ruta in [(1, "/paciente"), (3, "/medico"), (6, "/farmacia"), (7, "/admin")]:
        c.cookies.set("uid", str(uid))
        r = c.get(ruta)
        assert r.status_code == 200, ruta
