from fastapi import FastAPI, HTTPException
import asyncpg
import os

app = FastAPI(title="Inventario Service")

DB_DSN = os.getenv("DATABASE_URL", "postgresql://ticketuser:ticketpass@postgres:5432/ticketsdb")

pool = None


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seats (
                event_id TEXT PRIMARY KEY,
                available INTEGER NOT NULL
            )
        """)
        # Evento de ejemplo para las pruebas y la demo
        await conn.execute("""
            INSERT INTO seats (event_id, available)
            VALUES ('concierto-2026', 1)
            ON CONFLICT (event_id) DO NOTHING
        """)


@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inventario"}


@app.get("/inventory/{event_id}")
async def get_availability(event_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT available FROM seats WHERE event_id=$1", event_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        return {"event_id": event_id, "available": row["available"]}


@app.post("/inventory/{event_id}/reserve")
async def reserve_seat(event_id: str):
    async with pool.acquire() as conn:
        # NOTA: check-then-act sin lock a propósito.
        # Esta es la condición de carrera que se analiza en la Parte V (no se arregla aquí).
        row = await conn.fetchrow(
            "SELECT available FROM seats WHERE event_id=$1", event_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        if row["available"] <= 0:
            raise HTTPException(status_code=409, detail="No hay asientos disponibles")

        new_available = row["available"] - 1
        await conn.execute(
            "UPDATE seats SET available=$1 WHERE event_id=$2",
            new_available, event_id
        )
        return {"event_id": event_id, "reserved": True, "remaining": new_available}


@app.post("/inventory/{event_id}/reset")
async def reset_seats(event_id: str, amount: int = 1):
    """Endpoint auxiliar solo para reiniciar el inventario entre pruebas/demos."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO seats (event_id, available) VALUES ($1, $2)
            ON CONFLICT (event_id) DO UPDATE SET available=$2
            """,
            event_id, amount
        )
        return {"event_id": event_id, "available": amount}
