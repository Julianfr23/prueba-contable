from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import catalogos, comprobantes, exogena, libro_mayor
from app.core.config import get_settings
from app.infra.uvt_provider import actualizar_uvt

logging.basicConfig(level=logging.INFO)
settings = get_settings()


async def _loop_actualizacion_uvt() -> None:
    """
    Tarea periódica en background que mantiene actualizado el valor de la
    UVT del año actual (y el siguiente, útil cerca de fin de año) sin
    bloquear ninguna request HTTP. Ver app/infra/uvt_provider.py.
    """
    while True:
        anio_actual = datetime.now(timezone.utc).year
        for anio in (anio_actual, anio_actual + 1):
            try:
                await actualizar_uvt(anio)
            except Exception:  # noqa: BLE001
                logging.exception("Error refrescando UVT para %s", anio)
        await asyncio.sleep(settings.uvt_refresh_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(_loop_actualizacion_uvt())
    yield
    tarea.cancel()


app = FastAPI(title="API Aplicaciones Contables", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ver README: en producción restringir a los orígenes del frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalogos.router, prefix="/api")
app.include_router(comprobantes.router, prefix="/api")
app.include_router(libro_mayor.router, prefix="/api")
app.include_router(exogena.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
