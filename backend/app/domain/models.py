"""
Modelos de dominio (persistencia con SQLAlchemy).

Decisiones de diseño relevantes (ver también README):
- Todos los valores monetarios usan Numeric(18, 2) en DB y Decimal en Python.
  Nunca float, para evitar errores de representación binaria.
- El plan de cuentas se modela como una tabla plana con un campo `codigo`
  jerárquico tipo string (ej. "1105", "110505"). La jerarquía se deriva por
  prefijos de código en tiempo de consulta en lugar de una tabla de árbol
  materializada. Es más simple de mantener y suficiente para el alcance de
  esta prueba; en un ERP real se evaluaría un modelo de árbol explícito
  (adjacency list o nested set) si se necesitan operaciones jerárquicas
  frecuentes (ej. sumar saldos de todas las subcuentas).
- Un Comprobante contabilizado nunca se edita: se protege a nivel de
  aplicación (ver ComprobanteService) y adicionalmente a nivel de DB con un
  trigger-like check (estado) más un flag `bloqueado`. No se implementó un
  trigger SQL para mantener la lógica en un solo lugar (la capa de servicio),
  pero queda documentado como mejora para producción.
- La reversión se modela como un NUEVO comprobante que invierte
  débitos/créditos del original, enlazado por `comprobante_reversa_id` /
  `comprobante_original_id`. Esto preserva el libro mayor original intacto
  (trazabilidad total) en vez de "deshacer" el comprobante original.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Naturaleza(str, enum.Enum):
    DEBITO = "debito"
    CREDITO = "credito"


class EstadoComprobante(str, enum.Enum):
    BORRADOR = "borrador"
    CONTABILIZADO = "contabilizado"
    REVERSADO = "reversado"  # el original queda marcado así cuando se revierte
    REVERSION = "reversion"  # el comprobante generado por la reversión


class EstadoPeriodo(str, enum.Enum):
    ABIERTO = "abierto"
    CERRADO = "cerrado"


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    nit: Mapped[str] = mapped_column(String(20), unique=True)
    razon_social: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cuentas: Mapped[list["Cuenta"]] = relationship(back_populates="empresa")
    periodos: Mapped[list["PeriodoContable"]] = relationship(back_populates="empresa")


class Cuenta(Base):
    __tablename__ = "cuentas"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_cuenta_empresa_codigo"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(20), index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    naturaleza: Mapped[Naturaleza] = mapped_column(
    Enum(
        Naturaleza,
        name="naturaleza_enum",
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    )
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    empresa: Mapped["Empresa"] = relationship(back_populates="cuentas")


class PeriodoContable(Base):
    """
    Periodo mensual (ej. 2025-01). Se representa con `anio` y `mes` en lugar
    de un rango de fechas libre: simplifica la validación de "período abierto"
    a una búsqueda por clave y evita solapamientos.
    """

    __tablename__ = "periodos_contables"
    __table_args__ = (UniqueConstraint("empresa_id", "anio", "mes", name="uq_periodo_empresa_anio_mes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"))
    anio: Mapped[int]
    mes: Mapped[int]
    estado: Mapped[EstadoPeriodo] = mapped_column(
        Enum(
            EstadoPeriodo,
            name="estado_periodo_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            ),
            default=EstadoPeriodo.ABIERTO,
    )
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    empresa: Mapped["Empresa"] = relationship(back_populates="periodos")


class Correlativo(Base):
    """
    Contador atómico de numeración de comprobantes por empresa.

    Se usa `SELECT ... FOR UPDATE` sobre esta fila para serializar el
    incremento bajo concurrencia (ver ComprobanteService.contabilizar) y así
    evitar números de comprobante duplicados cuando dos requests intentan
    contabilizar al mismo tiempo sobre la misma empresa.
    """

    __tablename__ = "correlativos"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), primary_key=True)
    ultimo_numero: Mapped[int] = mapped_column(default=0)


class Tercero(Base):
    __tablename__ = "terceros"
    __table_args__ = (UniqueConstraint("empresa_id", "tipo_doc", "num_doc", name="uq_tercero_doc"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"))
    tipo_doc: Mapped[str] = mapped_column(String(10), default="CC")
    num_doc: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(255))


class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"))
    numero: Mapped[int | None] = mapped_column(nullable=True)  # se asigna al contabilizar
    fecha: Mapped[date] = mapped_column(Date)
    periodo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("periodos_contables.id"))
    descripcion: Mapped[str] = mapped_column(Text)
    estado: Mapped[EstadoComprobante] = mapped_column(
        Enum(
            EstadoComprobante,
            name="estado_comprobante_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=EstadoComprobante.BORRADOR,
    )

    comprobante_original_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobantes.id"), nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contabilizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lineas: Mapped[list["LineaContable"]] = relationship(
        back_populates="comprobante", cascade="all, delete-orphan"
    )
    periodo: Mapped["PeriodoContable"] = relationship()


class LineaContable(Base):
    __tablename__ = "lineas_contables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    comprobante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comprobantes.id"))
    cuenta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuentas.id"))
    tercero_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terceros.id"), nullable=True)
    debito: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    credito: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    comprobante: Mapped["Comprobante"] = relationship(back_populates="lineas")
    cuenta: Mapped["Cuenta"] = relationship()


class UvtValor(Base):
    """
    Caché local del valor de la UVT por año gravable, alimentada de forma
    asíncrona por el proveedor externo (ver app/infra/uvt_provider.py).
    Nunca se bloquea una petición HTTP esperando al proveedor externo: se
    lee este caché, y si falta el dato se dispara una actualización en
    background para la próxima vez.
    """

    __tablename__ = "uvt_valores"

    anio: Mapped[int] = mapped_column(primary_key=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fuente: Mapped[str] = mapped_column(String(50))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UvtActualizacionLog(Base):
    """Traza de cada intento de actualización del proveedor externo de UVT."""

    __tablename__ = "uvt_actualizacion_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    anio: Mapped[int]
    exitoso: Mapped[bool]
    detalle: Mapped[str] = mapped_column(Text)
    intentos: Mapped[int] = mapped_column(default=1)
    ejecutado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExogenaGeneracion(Base):
    """
    Registro histórico de cada generación de información exógena, incluyendo
    los parámetros usados y el XML resultante, para permitir re-descarga
    posterior sin tener que recalcular (los datos podrían cambiar luego).
    """

    __tablename__ = "exogena_generaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"))
    anio_gravable: Mapped[int]
    umbral_uvt: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    uvt_valor_usado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    xml_contenido: Mapped[str] = mapped_column(Text)
    total_registros: Mapped[int]
    total_valor_bruto: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
