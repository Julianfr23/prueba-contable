from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exogena_service import generar_exogena
from app.domain.models import ExogenaGeneracion
from app.domain.schemas import ExogenaGenerarRequest, ExogenaHistorialOut
from app.domain.validaciones import ReglaContableError
from app.infra.db import get_session

router = APIRouter(prefix="/exogena", tags=["exogena"])


@router.post("/generar")
async def generar(data: ExogenaGenerarRequest, session: AsyncSession = Depends(get_session)):
    try:
        generacion = await generar_exogena(
            session, data.empresa_id, data.anio_gravable, data.umbral_uvt
        )
    except ReglaContableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(
        content=generacion.xml_contenido,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="exogena_{data.anio_gravable}_{generacion.id}.xml"',
            "X-Generacion-Id": str(generacion.id),
        },
    )


@router.get("/historial", response_model=list[ExogenaHistorialOut])
async def historial(empresa_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ExogenaGeneracion)
        .where(ExogenaGeneracion.empresa_id == empresa_id)
        .order_by(ExogenaGeneracion.generado_en.desc())
    )
    return result.scalars().all()


@router.get("/historial/{generacion_id}/archivo")
async def descargar_archivo(generacion_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    generacion = await session.get(ExogenaGeneracion, generacion_id)
    if generacion is None:
        raise HTTPException(status_code=404, detail="Generación no encontrada")
    return Response(
        content=generacion.xml_contenido,
        media_type="application/xml",
        headers={
            "Content-Disposition": (
                f'attachment; filename="exogena_{generacion.anio_gravable}_{generacion.id}.xml"'
            )
        },
    )
