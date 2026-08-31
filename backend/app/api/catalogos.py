from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.comprobante_service import cerrar_periodo
from app.domain.models import Cuenta, Empresa
from app.domain.schemas import CuentaCreate, CuentaOut, EmpresaCreate, EmpresaOut, PeriodoOut
from app.domain.validaciones import ReglaContableError
from app.infra.db import get_session

router = APIRouter(tags=["catalogos"])


@router.post("/empresas", response_model=EmpresaOut)
async def crear_empresa(data: EmpresaCreate, session: AsyncSession = Depends(get_session)):
    empresa = Empresa(nit=data.nit, razon_social=data.razon_social)
    session.add(empresa)
    await session.commit()
    await session.refresh(empresa)
    return empresa


@router.get("/empresas", response_model=list[EmpresaOut])
async def listar_empresas(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Empresa))
    return result.scalars().all()


@router.post("/empresas/{empresa_id}/cuentas", response_model=CuentaOut)
async def crear_cuenta(
    empresa_id: uuid.UUID, data: CuentaCreate, session: AsyncSession = Depends(get_session)
):
    cuenta = Cuenta(empresa_id=empresa_id, **data.model_dump())
    session.add(cuenta)
    await session.commit()
    await session.refresh(cuenta)
    return cuenta


@router.get("/empresas/{empresa_id}/cuentas", response_model=list[CuentaOut])
async def listar_cuentas(empresa_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Cuenta).where(Cuenta.empresa_id == empresa_id))
    return result.scalars().all()


@router.post("/empresas/{empresa_id}/periodos/{anio}/{mes}/cerrar", response_model=PeriodoOut)
async def cerrar_periodo_endpoint(
    empresa_id: uuid.UUID, anio: int, mes: int, session: AsyncSession = Depends(get_session)
):
    try:
        return await cerrar_periodo(session, empresa_id, anio, mes)
    except ReglaContableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
