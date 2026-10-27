# SaludIA: asistente inteligente para la gestión de servicios de salud

Prototipo funcional de la actividad **"Orquestando Códigos: La Sinfonía de los Sistemas"** del curso *Arquitectura de Software* (Corporación Tecnológica del Oriente).

**Integrantes:** Yeison Stiven Gutiérrez Rozo y Michael Yesid Torres Bello.

SaludIA apoya a una IPS en tres procesos:

1. **Asignación de citas:** el paciente consulta la agenda disponible, programa y cancela citas.
2. **Orientación de síntomas con IA:** un asistente clasifica la urgencia (alta, media o baja) y sugiere la especialidad. *Orienta, no diagnostica.*
3. **Diagnóstico y dispensación:** el médico registra el diagnóstico (CIE-10) y la fórmula, y la farmacia la dispensa y descuenta el inventario.

Además, un **tablero de control** muestra indicadores y el estado de resiliencia del sistema.

## Arquitectura

Monolito modular en capas, listo para la nube:

```
app/
├── main.py              # Punto de entrada y endpoint /health
├── config.py            # Configuración por variables de entorno
├── container.py         # Composición de dependencias
├── domain/models.py     # Entidades: Paciente, Médico, Cita, Diagnóstico, Fórmula...
├── repositories/        # Patrón Repository (implementación en memoria)
├── services/
│   ├── clinica.py       # Citas, atención médica, farmacia y tablero
│   └── asistente.py     # Asistente IA (Strategy + Circuit Breaker)
├── resilience/          # Circuit Breaker
├── api/
│   ├── rest.py          # API REST /api/v1 (Swagger en /docs)
│   └── web.py           # Vistas web por rol
├── templates/           # Plantillas HTML (Jinja2)
└── static/              # Estilos
tests/                   # Pruebas automáticas (pytest)
docs/diagramas/          # Diagramas UML en PlantUML y PNG
```

### Patrones aplicados

| Patrón | Dónde | Para qué |
| --- | --- | --- |
| Arquitectura en capas | `api` → `services` → `repositories` → `domain` | Separar responsabilidades y bajar el acoplamiento |
| Repository | `app/repositories/memory.py` | Cambiar el almacenamiento (memoria → base de datos en la nube) sin tocar la lógica |
| Strategy | `MotorReglas` / `MotorExterno` en `asistente.py` | Intercambiar el motor de IA sin cambiar el servicio |
| Circuit Breaker | `app/resilience/circuit_breaker.py` | Si el proveedor de IA falla, el asistente responde con el motor de respaldo |
| Health Endpoint Monitoring | `GET /health` | La plataforma en la nube verifica que la app esté viva |
| External Configuration Store | `app/config.py`, variables de entorno | El mismo código corre en local y en la nube |

## Ejecutar en local

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Abra <http://localhost:8000>. Seleccione un usuario de prueba:

| Usuario | Rol | Qué probar |
| --- | --- | --- |
| Laura Martínez | Paciente | Asistente IA, solicitar y cancelar citas, ver fórmulas |
| Dra. Ana Gómez | Médico | Atender cita, registrar diagnóstico y fórmula |
| Andrés Peña | Farmacéutico | Dispensar fórmulas, alertas de stock bajo |
| Administrador IPS | Administrador | Tablero de indicadores y estado del Circuit Breaker |

Otras rutas: documentación de la API en `/docs` y monitoreo en `/health`.

### Pruebas

```bash
pytest -q
```

### Demostrar el Circuit Breaker

```bash
SIMULAR_FALLA_IA=true CB_UMBRAL_FALLAS=3 uvicorn app.main:app
```

Haga 3 consultas al asistente: todas responden con el motor `reglas (respaldo)` y el tablero muestra el circuito **abierto**.

## Despliegue en la nube (Render)

1. Suba este repositorio a GitHub.
2. En <https://render.com>, elija **New → Blueprint** y seleccione el repositorio; Render lee `render.yaml`.
3. Espere el despliegue y abra la URL pública (`https://saludia-xxxx.onrender.com`).

El plan gratuito se suspende tras unos minutos sin uso; la primera visita puede tardar cerca de un minuto.

## Variables de entorno

Ver `.env.example`. Las principales: `APP_ENTORNO`, `IA_PROVEEDOR_URL`, `SIMULAR_FALLA_IA`, `CB_UMBRAL_FALLAS`, `CB_TIEMPO_RECUPERACION`, `STOCK_MINIMO`.

## Alcance del prototipo

Implementa 13 de los 14 requisitos funcionales del informe (todos menos RF-14, recordatorios de cita). Los datos se guardan en memoria y se reinician al reiniciar el servicio; el ingreso es simulado con usuarios de prueba. En producción se agregaría base de datos administrada, autenticación OAuth 2.0 y cifrado de datos clínicos (Ley 1581 de 2012).
