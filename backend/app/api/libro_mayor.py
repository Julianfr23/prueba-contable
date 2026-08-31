from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.libro_mayor_service import consultar_libro_mayor
from app.domain.schemas import MovimientoLibroMayor
from app.infra.db import get_session

router = APIRouter(prefix="/libro-mayor", tags=["libro-mayor"])


@router.get("", response_model=list[MovimientoLibroMayor])
async def obtener_libro_mayor(
    empresa_id: uuid.UUID,
    cuenta_id: uuid.UUID,
    fecha_inicio: date = Query(...),
    fecha_fin: date = Query(...),
    session: AsyncSession = Depends(get_session),
):
    return await consultar_libro_mayor(session, empresa_id, cuenta_id, fecha_inicio, fecha_fin)
