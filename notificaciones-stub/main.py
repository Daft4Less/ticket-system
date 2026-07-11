from fastapi import FastAPI, HTTPException
import asyncio
import random

app = FastAPI(title="Notificaciones Stub Service")

LATENCY_MIN = 0.1
LATENCY_MAX = 1.0
FAILURE_RATE = 0.20  # 20% de probabilidad de fallo, para el escenario "Correo Perdido"

# Modo "caído": simula que el servicio está completamente inactivo
down_mode = {"enabled": False}


@app.get("/health")
async def health():
    if down_mode["enabled"]:
        raise HTTPException(status_code=503, detail="Servicio de notificaciones inactivo")
    return {"status": "ok", "service": "notificaciones-stub"}


@app.post("/notifications/send-confirmation")
async def send_confirmation(event_id: str, email: str = "cliente@example.com"):
    if down_mode["enabled"]:
        raise HTTPException(status_code=503, detail="Servicio de notificaciones inactivo")

    await asyncio.sleep(random.uniform(LATENCY_MIN, LATENCY_MAX))

    if random.random() < FAILURE_RATE:
        raise HTTPException(status_code=503, detail="Fallo simulado al enviar el correo")

    return {"event_id": event_id, "email": email, "status": "sent"}


@app.post("/chaos/down-mode")
async def toggle_down_mode(enabled: bool):
    """Endpoint para simular el escenario 'Correo Perdido': el servicio queda inactivo."""
    down_mode["enabled"] = enabled
    return {"down_mode": down_mode}
