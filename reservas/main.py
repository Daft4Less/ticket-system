from fastapi import FastAPI, HTTPException
import httpx
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

app = FastAPI(title="Reservas Service (Core)")

INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://inventario:8000")
PAGOS_URL = os.getenv("PAGOS_URL", "http://pagos-stub:8000")
NOTIFICACIONES_URL = os.getenv("NOTIFICACIONES_URL", "http://notificaciones-stub:8000")

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class InventarioUnavailableError(Exception):
    """Se lanza cuando Inventario no responde o responde 503 (fallo técnico, no de negocio)."""
    pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reservas"}


# --- Patrón de resiliencia: Retry con backoff exponencial ---
# Corresponde al fallo "Inventario Fantasma" (Parte II, fallo #1).
# Justificación: el crash de un pod suele ser transitorio (Kubernetes lo reinicia
# o balancea hacia la réplica sana en el otro nodo); reintentar con espera creciente
# le da al sistema tiempo real de recuperarse antes de fallar la compra completa.
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(InventarioUnavailableError),
    reraise=True,
)
async def reservar_inventario(event_id: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(f"{INVENTARIO_URL}/inventory/{event_id}/reserve")
        except httpx.RequestError as e:
            raise InventarioUnavailableError(f"Inventario no disponible: {e}")

        if resp.status_code == 503:
            raise InventarioUnavailableError("Inventario respondió 503 (posible pod caído)")

        if resp.status_code != 200:
            # Error de negocio (ej. 409 sin asientos) - NO se reintenta, se propaga directo
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.json().get("detail", "Error en inventario")
            )

        return resp.json()


@app.post("/reservations/purchase")
async def purchase(event_id: str, email: str = "cliente@example.com", amount: float = 10.0):
    result = {"event_id": event_id, "steps": {}}

    # Paso 1: reservar el asiento en Inventario (con retry + backoff)
    try:
        result["steps"]["inventario"] = await reservar_inventario(event_id)
    except InventarioUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Inventario no disponible tras reintentos: {e}")

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
