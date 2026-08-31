from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Comprobante, EstadoComprobante, LineaContable, Tercero
from app.domain.schemas import MovimientoLibroMayor

"""
Estrategia de cálculo de saldo acumulado: cálculo EN TIEMPO REAL a partir de
los movimientos, ordenados por fecha y luego por número de comprobante.

Por qué esta estrategia y no saldos materializados (ej. tabla de acumulados
por cuenta/período):
- Consistencia: el saldo siempre refleja el estado real de los comprobantes
  contabilizados, sin riesgo de que un acumulado quede desincronizado tras
  una reversión o un error parcial.
- Simplicidad y corrección primero: para el volumen esperado en esta prueba,
  una consulta sobre líneas contables con índices adecuados (cuenta_id,
  fecha) es suficiente en rendimiento.
- Trade-off asumido: en un libro mayor con millones de movimientos por
  cuenta, este enfoque encarece la consulta de "saldo a una fecha". La
  mitigación natural sería mantener saldos acumulados por cierre de período
  (snapshot) y sumar solo los movimientos posteriores al último snapshot;
  eso introduce el riesgo de inconsistencia si el snapshot no se actualiza
  atómicamente con el cierre, por lo que se dejó fuera del alcance de esta
  entrega y se documenta aquí como la mejora a implementar si el volumen lo
  exige.
"""


async def consultar_libro_mayor(
    session: AsyncSession,
    empresa_id: uuid.UUID,
    cuenta_id: uuid.UUID,
    fecha_inicio: date,
    fecha_fin: date,
) -> list[MovimientoLibroMayor]:
    stmt = (
        select(LineaContable, Comprobante, Tercero)
        .join(Comprobante, LineaContable.comprobante_id == Comprobante.id)
        .outerjoin(Tercero, LineaContable.tercero_id == Tercero.id)
        .where(
            Comprobante.empresa_id == empresa_id,
            LineaContable.cuenta_id == cuenta_id,
            Comprobante.estado.in_([EstadoComprobante.CONTABILIZADO, EstadoComprobante.REVERSION]),
            Comprobante.fecha >= fecha_inicio,
            Comprobante.fecha <= fecha_fin,
        )
        .order_by(Comprobante.fecha.asc(), Comprobante.numero.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    movimientos: list[MovimientoLibroMayor] = []
    saldo = Decimal("0")
    for linea, comprobante, tercero in rows:
        saldo += linea.debito - linea.credito
        movimientos.append(
            MovimientoLibroMayor(
                fecha=comprobante.fecha,
                numero=comprobante.numero,
                comprobante_id=comprobante.id,
                descripcion=comprobante.descripcion,
                tercero=tercero.nombre if tercero else None,
                debito=linea.debito,
                credito=linea.credito,
                saldo_acumulado=saldo,
            )
        )
    return movimientos
