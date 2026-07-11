from fastapi import FastAPI, HTTPException
import httpx
import os

app = FastAPI(title="API Gateway")

RESERVAS_URL = os.getenv("RESERVAS_URL", "http://reservas:8000")

TIMEOUT = httpx.Timeout(15.0, connect=5.0)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.post("/purchase")
async def purchase(event_id: str, email: str = "cliente@example.com", amount: float = 10.0):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{RESERVAS_URL}/reservations/purchase",
                params={"event_id": event_id, "email": email, "amount": amount}
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Servicio de Reservas no disponible: {e}")

        return resp.json() if resp.status_code == 200 else HTTPException(
            status_code=resp.status_code, detail=resp.text
        )
