from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Comprobante,
    Correlativo,
    EstadoComprobante,
    EstadoPeriodo,
    LineaContable,
    PeriodoContable,
)
from app.domain.schemas import ComprobanteCreate
from app.domain.validaciones import LineaValidable, ReglaContableError, validar_comprobante_para_contabilizar


async def _get_or_create_periodo(session: AsyncSession, empresa_id: uuid.UUID, fecha) -> PeriodoContable:
    result = await session.execute(
        select(PeriodoContable).where(
            PeriodoContable.empresa_id == empresa_id,
            PeriodoContable.anio == fecha.year,
            PeriodoContable.mes == fecha.month,
        )
    )
    periodo = result.scalar_one_or_none()
    if periodo is None:
        periodo = PeriodoContable(empresa_id=empresa_id, anio=fecha.year, mes=fecha.month)
        session.add(periodo)
        await session.flush()
    return periodo


async def crear_borrador(session: AsyncSession, data: ComprobanteCreate) -> Comprobante:
    periodo = await _get_or_create_periodo(session, data.empresa_id, data.fecha)

    comprobante = Comprobante(
        empresa_id=data.empresa_id,
        fecha=data.fecha,
        periodo_id=periodo.id,
        descripcion=data.descripcion,
        estado=EstadoComprobante.BORRADOR,
    )
    comprobante.lineas = [
        LineaContable(
            cuenta_id=linea.cuenta_id,
            tercero_id=linea.tercero_id,
            debito=linea.debito,
            credito=linea.credito,
            descripcion=linea.descripcion,
        )
        for linea in data.lineas
    ]
    session.add(comprobante)
    await session.commit()
    await session.refresh(comprobante, attribute_names=["lineas"])
    return comprobante


async def _siguiente_numero(session: AsyncSession, empresa_id: uuid.UUID) -> int:
    """
    Incrementa el correlativo de forma atómica usando SELECT ... FOR UPDATE.

    Esto serializa la asignación de números bajo concurrencia: si dos
    transacciones intentan contabilizar comprobantes de la misma empresa al
    mismo tiempo, la segunda espera a que la primera libere el lock de fila
    antes de leer el valor, garantizando numeración sin duplicados ni huecos
    por condiciones de carrera.

    Es una solución intencionalmente simple (no requiere colas ni locks
    distribuidos) apropiada para el volumen de esta prueba. En un sistema de
    alto throughput se evaluaría una secuencia de PostgreSQL nativa o un
    esquema de particionamiento por empresa.
    """
    result = await session.execute(
        select(Correlativo).where(Correlativo.empresa_id == empresa_id).with_for_update()
    )
    correlativo = result.scalar_one_or_none()
    if correlativo is None:
        correlativo = Correlativo(empresa_id=empresa_id, ultimo_numero=0)
        session.add(correlativo)
        await session.flush()
    correlativo.ultimo_numero += 1
    return correlativo.ultimo_numero


async def contabilizar(session: AsyncSession, comprobante_id: uuid.UUID) -> Comprobante:
    result = await session.execute(
        select(Comprobante)
        .where(Comprobante.id == comprobante_id)
        .with_for_update()
    )
    comprobante = result.scalar_one_or_none()
    if comprobante is None:
        raise ReglaContableError("Comprobante no encontrado")
    if comprobante.estado != EstadoComprobante.BORRADOR:
        raise ReglaContableError(
            f"Solo se pueden contabilizar comprobantes en borrador (estado actual: {comprobante.estado.value})"
        )

    await session.refresh(comprobante, attribute_names=["lineas"])

    periodo = await session.get(PeriodoContable, comprobante.periodo_id)

    # Cargar las cuentas usadas para validar que estén activas.
    from app.domain.models import Cuenta  # import local para evitar ciclos

    cuenta_ids = {linea.cuenta_id for linea in comprobante.lineas}
    cuentas_result = await session.execute(select(Cuenta).where(Cuenta.id.in_(cuenta_ids)))
    cuentas_por_id = {c.id: c for c in cuentas_result.scalars().all()}

    lineas_validables = [
        LineaValidable(
            cuenta_id=str(linea.cuenta_id),
            cuenta_activa=cuentas_por_id[linea.cuenta_id].activa,
            debito=linea.debito,
            credito=linea.credito,
        )
        for linea in comprobante.lineas
    ]

    validar_comprobante_para_contabilizar(lineas_validables, periodo.estado.value)

    comprobante.numero = await _siguiente_numero(session, comprobante.empresa_id)
    comprobante.estado = EstadoComprobante.CONTABILIZADO
    comprobante.contabilizado_en = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(comprobante, attribute_names=["lineas"])
    return comprobante


async def revertir(session: AsyncSession, comprobante_id: uuid.UUID, motivo: str) -> Comprobante:
    """
    Estrategia de reversión: se crea un NUEVO comprobante contabilizado que
    invierte cada línea (débito <-> crédito) del original, y queda enlazado
    a él mediante `comprobante_original_id`. El comprobante original se
    marca como REVERSADO pero NUNCA se borra ni se modifica su contenido.

    Por qué esta estrategia y no "anular" el original:
    - Preserva el libro mayor tal como ocurrió: cualquier auditoría puede
      ver el movimiento original y su corrección como dos hechos distintos,
      igual que se haría en un libro contable físico.
    - El nuevo comprobante de reversión respeta el mismo período que el
      original, o el período vigente si el original ya cerró — aquí se
      usa el período de la fecha actual para no reabrir períodos cerrados.
    """
    result = await session.execute(
        select(Comprobante).where(Comprobante.id == comprobante_id).with_for_update()
    )
    original = result.scalar_one_or_none()
    if original is None:
        raise ReglaContableError("Comprobante no encontrado")
    if original.estado != EstadoComprobante.CONTABILIZADO:
        raise ReglaContableError("Solo se pueden revertir comprobantes contabilizados")

    await session.refresh(original, attribute_names=["lineas"])

    hoy = datetime.now(timezone.utc).date()
    periodo_reversion = await _get_or_create_periodo(session, original.empresa_id, hoy)

    reversion = Comprobante(
        empresa_id=original.empresa_id,
        fecha=hoy,
        periodo_id=periodo_reversion.id,
        descripcion=f"Reversión de comprobante {original.numero}: {motivo}",
        estado=EstadoComprobante.BORRADOR,
        comprobante_original_id=original.id,
    )
    reversion.lineas = [
        LineaContable(
            cuenta_id=linea.cuenta_id,
            tercero_id=linea.tercero_id,
            debito=linea.credito,
            credito=linea.debito,
            descripcion=f"Reversión: {linea.descripcion or ''}".strip(),
        )
        for linea in original.lineas
    ]
    session.add(reversion)
    await session.flush()

    original.estado = EstadoComprobante.REVERSADO
    await session.commit()

    reversion_contabilizada = await contabilizar(session, reversion.id)
    reversion_contabilizada.estado = EstadoComprobante.REVERSION
    await session.commit()
    await session.refresh(reversion_contabilizada, attribute_names=["lineas"])
    return reversion_contabilizada


async def cerrar_periodo(session: AsyncSession, empresa_id: uuid.UUID, anio: int, mes: int) -> PeriodoContable:
    periodo = await _get_or_create_periodo(session, empresa_id, datetime(anio, mes, 1).date())
    if periodo.estado == EstadoPeriodo.CERRADO:
        raise ReglaContableError("El período ya está cerrado")
    periodo.estado = EstadoPeriodo.CERRADO
    periodo.cerrado_en = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(periodo)
    return periodo
