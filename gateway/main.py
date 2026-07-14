from fastapi import FastAPI, HTTPException
import httpx
import os
import asyncio

app = FastAPI(title="API Gateway")

RESERVAS_URL = os.getenv("RESERVAS_URL", "http://reservas:8000")
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# --- Patrón de resiliencia: Bulkhead ---
# Corresponde al fallo "Diluvio de Peticiones" (Parte II, fallo #3).
# Justificación: ante un pico de tráfico, dejar que todas las peticiones entren sin
# límite agota conexiones/recursos y puede colapsar Reservas y los servicios detrás.
# El bulkhead limita cuántas peticiones concurrentes procesa el Gateway a la vez;
# el resto se rechaza rápido con 503 en vez de encolarse indefinidamente.
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
bulkhead_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.post("/purchase")
async def purchase(event_id: str, email: str = "cliente@example.com", amount: float = 10.0):
    # Intento no bloqueante de adquirir un "slot" del bulkhead

    try:
        await asyncio.wait_for(bulkhead_semaphore.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail=f"Gateway saturado: ya hay {MAX_CONCURRENT_REQUESTS} peticiones en proceso. Intenta de nuevo."
        )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                resp = await client.post(
                    f"{RESERVAS_URL}/reservations/purchase",
                    params={"event_id": event_id, "email": email, "amount": amount}
                )
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Servicio de Reservas no disponible: {e}")

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            return resp.json()
    finally:
        bulkhead_semaphore.release()
