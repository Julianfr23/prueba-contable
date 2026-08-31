"""
Integración externa: valor de la UVT (Unidad de Valor Tributario) por año.

Diseño:
- `UvtProvider` es una interfaz simple con dos implementaciones:
  `UvtProviderSimulado` (por defecto, para que la prueba sea reproducible
  sin depender de disponibilidad de terceros) y `UvtProviderHttp` (llama a
  una URL configurable que retorne el valor).
- La actualización SIEMPRE ocurre en una tarea de background
  (`asyncio.create_task`, disparada al iniciar la app y periódicamente), NUNCA
  dentro del ciclo request/response. Los endpoints que necesitan el valor de
  la UVT leen la tabla `uvt_valores` (caché local); si no hay un valor para
  el año solicitado, se dispara una actualización en background y se le
  informa al usuario que puede reintentar en unos segundos, en lugar de
  bloquear la request esperando al proveedor externo.
- Reintentos: `_con_reintentos` aplica backoff exponencial simple ante
  fallos transitorios (timeouts, 5xx). Cada intento (exitoso o no) se
  registra en `uvt_actualizacion_log` para trazabilidad.
- Idempotencia: `actualizar_uvt` hace un upsert por año (clave primaria
  `anio` en `uvt_valores`), de modo que ejecuciones repetidas para el mismo
  año no generan duplicados, solo refrescan `actualizado_en`.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.domain.models import UvtActualizacionLog, UvtValor
from app.infra.db import AsyncSessionLocal

logger = logging.getLogger("uvt_provider")

# Valores de referencia usados por el proveedor simulado. En producción esto
# vendría de la fuente real (API/página de la DIAN).
_VALORES_SIMULADOS: dict[int, Decimal] = {
    2023: Decimal("42412"),
    2024: Decimal("47065"),
    2025: Decimal("49799"),
    2026: Decimal("52234"),
}


class UvtProviderError(Exception):
    pass


class UvtProvider(ABC):
    @abstractmethod
    async def obtener_valor(self, anio: int) -> Decimal:
        ...


class UvtProviderSimulado(UvtProvider):
    """Simula una integración externa real, incluyendo fallos ocasionales."""

    async def obtener_valor(self, anio: int) -> Decimal:
        await asyncio.sleep(0.05)  # simula latencia de red
        if anio in _VALORES_SIMULADOS:
            return _VALORES_SIMULADOS[anio]
        raise UvtProviderError(f"No existe valor simulado de UVT para el año {anio}")


class UvtProviderHttp(UvtProvider):
    def __init__(self, url: str):
        self.url = url

    async def obtener_valor(self, anio: int) -> Decimal:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(self.url, params={"anio": anio})
            resp.raise_for_status()
            data = resp.json()
            return Decimal(str(data["valor"]))


def get_provider() -> UvtProvider:
    settings = get_settings()
    if settings.uvt_provider == "http" and settings.uvt_provider_url:
        return UvtProviderHttp(settings.uvt_provider_url)
    return UvtProviderSimulado()


async def _con_reintentos(anio: int, intentos_max: int = 3) -> tuple[Decimal | None, int, str]:
    provider = get_provider()
    ultimo_error = ""
    for intento in range(1, intentos_max + 1):
        try:
            valor = await provider.obtener_valor(anio)
            return valor, intento, "ok"
        except Exception as exc:  # noqa: BLE001 - se registra y se reintenta
            ultimo_error = str(exc)
            logger.warning("Fallo intento %s/%s obteniendo UVT %s: %s", intento, intentos_max, anio, exc)
            if intento < intentos_max:
                await asyncio.sleep(0.2 * (2 ** (intento - 1)))  # backoff exponencial
    return None, intentos_max, ultimo_error


async def actualizar_uvt(anio: int) -> UvtValor | None:
    """
    Ejecuta la actualización (con reintentos) y persiste el resultado y su
    traza. Diseñada para llamarse desde una tarea de background, nunca desde
    el hilo de una request HTTP síncrona.
    """
    valor, intentos, detalle = await _con_reintentos(anio)

    async with AsyncSessionLocal() as session:
        session.add(
            UvtActualizacionLog(
                anio=anio,
                exitoso=valor is not None,
                detalle=detalle,
                intentos=intentos,
            )
        )
        resultado = None
        if valor is not None:
            stmt = (
                pg_insert(UvtValor)
                .values(anio=anio, valor=valor, fuente=get_provider().__class__.__name__)
                .on_conflict_do_update(
                    index_elements=[UvtValor.anio],
                    set_={"valor": valor, "fuente": get_provider().__class__.__name__},
                )
                .returning(UvtValor)
            )
            resultado = (await session.execute(stmt)).scalar_one()
        await session.commit()
        return resultado


async def obtener_uvt_cacheado(session, anio: int) -> UvtValor | None:
    result = await session.execute(select(UvtValor).where(UvtValor.anio == anio))
    return result.scalar_one_or_none()


def disparar_actualizacion_en_background(anio: int) -> None:
    """Dispara la actualización sin esperar el resultado (fire-and-forget)."""
    asyncio.create_task(actualizar_uvt(anio))
