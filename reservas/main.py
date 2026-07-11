from fastapi import FastAPI, HTTPException
import httpx
import os

app = FastAPI(title="Reservas Service (Core)")

INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://inventario:8000")
PAGOS_URL = os.getenv("PAGOS_URL", "http://pagos-stub:8000")
NOTIFICACIONES_URL = os.getenv("NOTIFICACIONES_URL", "http://notificaciones-stub:8000")

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reservas"}


@app.post("/reservations/purchase")
async def purchase(event_id: str, email: str = "cliente@example.com", amount: float = 10.0):
    result = {"event_id": event_id, "steps": {}}

    # Paso 1: reservar el asiento en Inventario
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(f"{INVENTARIO_URL}/inventory/{event_id}/reserve")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Inventario no disponible: {e}")

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Error en inventario"))

        result["steps"]["inventario"] = resp.json()

    # Paso 2: procesar el pago
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(f"{PAGOS_URL}/payments/charge", params={"event_id": event_id, "amount": amount})
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Pagos no disponible: {e}")

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Error en el pago"))

        result["steps"]["pago"] = resp.json()

    # Paso 3: enviar notificación — si falla, NO se revierte la compra (fallo no crítico)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{NOTIFICACIONES_URL}/notifications/send-confirmation",
                params={"event_id": event_id, "email": email}
            )
            if resp.status_code == 200:
                result["steps"]["notificacion"] = resp.json()
            else:
                result["steps"]["notificacion"] = {"status": "failed", "detail": resp.json().get("detail")}
        except httpx.RequestError as e:
            result["steps"]["notificacion"] = {"status": "failed", "detail": str(e)}

    result["purchase_status"] = "completed"
    return result
