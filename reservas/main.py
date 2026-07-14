from fastapi import FastAPI, HTTPException
import httpx
import os
from datetime import timedelta
from aiobreaker import CircuitBreaker, CircuitBreakerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

app = FastAPI(title="Reservas Service (Core)")

INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://inventario:8000")
PAGOS_URL = os.getenv("PAGOS_URL", "http://pagos-stub:8000")
NOTIFICACIONES_URL = os.getenv("NOTIFICACIONES_URL", "http://notificaciones-stub:8000")

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
PAGOS_TIMEOUT = httpx.Timeout(3.0, connect=2.0)


class InventarioUnavailableError(Exception):
    pass


class PagosUnavailableError(Exception):
    """Se lanza cuando Pagos no responde a tiempo o falla (contada como fallo por el circuit breaker)."""
    pass


# --- Patrón de resiliencia: Circuit Breaker (aiobreaker, con soporte nativo de asyncio) ---
# Corresponde al fallo "Pasarela Lenta" (Parte II, fallo #2).
pagos_breaker = CircuitBreaker(fail_max=3, timeout_duration=timedelta(seconds=30))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reservas"}


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
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.json().get("detail", "Error en inventario")
            )

        return resp.json()


@pagos_breaker
async def llamar_pagos(event_id: str, amount: float) -> dict:
    async with httpx.AsyncClient(timeout=PAGOS_TIMEOUT) as client:
        try:
            resp = await client.post(f"{PAGOS_URL}/payments/charge", params={"event_id": event_id, "amount": amount})
        except httpx.TimeoutException:
            raise PagosUnavailableError("Pagos no respondió a tiempo (posible pasarela lenta)")
        except httpx.RequestError as e:
            raise PagosUnavailableError(f"Pagos no disponible: {e}")

        if resp.status_code != 200:
            raise PagosUnavailableError(resp.json().get("detail", "Error en el pago"))

        return resp.json()


@app.post("/reservations/purchase")
async def purchase(event_id: str, email: str = "cliente@example.com", amount: float = 10.0):
    result = {"event_id": event_id, "steps": {}}

    try:
        result["steps"]["inventario"] = await reservar_inventario(event_id)
    except InventarioUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Inventario no disponible tras reintentos: {e}")

    try:
        result["steps"]["pago"] = await llamar_pagos(event_id, amount)
    except CircuitBreakerError:
        raise HTTPException(
            status_code=503,
            detail="Pasarela de pagos temporalmente inhabilitada (circuit breaker abierto). Intenta de nuevo en unos segundos."
        )
    except PagosUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

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
