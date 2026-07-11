from fastapi import FastAPI, HTTPException
import asyncio
import random

app = FastAPI(title="Pagos Stub Service")

# Configuración del comportamiento simulado (ajustable por variables de entorno más adelante)
LATENCY_MIN = 0.2   # segundos
LATENCY_MAX = 2.0    # segundos normales
FAILURE_RATE = 0.15   # 15% de probabilidad de fallo aleatorio

# Modo "pasarela lenta": se activa manualmente para el escenario de chaos testing
slow_mode = {"enabled": False, "delay_seconds": 20}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pagos-stub"}


@app.post("/payments/charge")
async def charge(event_id: str, amount: float = 10.0):
    # Si el modo lento está activo, simula la "Pasarela Lenta" del catálogo de fallos
    if slow_mode["enabled"]:
        await asyncio.sleep(slow_mode["delay_seconds"])
    else:
        await asyncio.sleep(random.uniform(LATENCY_MIN, LATENCY_MAX))

    if random.random() < FAILURE_RATE:
        raise HTTPException(status_code=503, detail="Fallo simulado en el procesador de pagos")

    return {"event_id": event_id, "amount": amount, "status": "approved"}


@app.post("/chaos/slow-mode")
async def toggle_slow_mode(enabled: bool, delay_seconds: int = 20):
    """Endpoint para activar/desactivar el escenario 'Pasarela Lenta' durante la demo."""
    slow_mode["enabled"] = enabled
    slow_mode["delay_seconds"] = delay_seconds
    return {"slow_mode": slow_mode}
