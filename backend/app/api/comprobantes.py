from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import comprobante_service
from app.domain.schemas import ComprobanteCreate, ComprobanteOut
from app.domain.validaciones import ReglaContableError
from app.infra.db import get_session

router = APIRouter(prefix="/comprobantes", tags=["comprobantes"])


class RevertirRequest(BaseModel):
    motivo: str


@router.post("", response_model=ComprobanteOut)
async def crear_borrador(data: ComprobanteCreate, session: AsyncSession = Depends(get_session)):
    return await comprobante_service.crear_borrador(session, data)


@router.post("/{comprobante_id}/contabilizar", response_model=ComprobanteOut)
async def contabilizar(comprobante_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    try:
        return await comprobante_service.contabilizar(session, comprobante_id)
    except ReglaContableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{comprobante_id}/revertir", response_model=ComprobanteOut)
async def revertir(
    comprobante_id: uuid.UUID, data: RevertirRequest, session: AsyncSession = Depends(get_session)
):
    try:
        return await comprobante_service.revertir(session, comprobante_id, data.motivo)
    except ReglaContableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
