from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.domain.models import EstadoComprobante, EstadoPeriodo, Naturaleza


# ---------- Empresa / Cuenta ----------
class EmpresaCreate(BaseModel):
    nit: str
    razon_social: str


class EmpresaOut(BaseModel):
    id: uuid.UUID
    nit: str
    razon_social: str

    class Config:
        from_attributes = True


class CuentaCreate(BaseModel):
    codigo: str
    nombre: str
    naturaleza: Naturaleza


class CuentaOut(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    naturaleza: Naturaleza
    activa: bool

    class Config:
        from_attributes = True

# ---------- Tercero ----------
class TerceroCreate(BaseModel):
    tipo_doc: str = "CC"
    num_doc: str
    nombre: str


class TerceroOut(BaseModel):
    id: uuid.UUID
    tipo_doc: str
    num_doc: str
    nombre: str

    class Config:
        from_attributes = True


# ---------- Periodo ----------
class PeriodoOut(BaseModel):
    id: uuid.UUID
    anio: int
    mes: int
    estado: EstadoPeriodo

    class Config:
        from_attributes = True


# ---------- Comprobante ----------
class LineaCreate(BaseModel):
    cuenta_id: uuid.UUID
    tercero_id: uuid.UUID | None = None
    debito: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    credito: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    descripcion: str | None = None

    @model_validator(mode="after")
    def no_debito_y_credito_simultaneo(self) -> "LineaCreate":
        if self.debito > 0 and self.credito > 0:
            raise ValueError("Una línea no puede tener débito y crédito simultáneamente")
        if self.debito == 0 and self.credito == 0:
            raise ValueError("Una línea debe tener débito o crédito mayor a cero")
        return self


class ComprobanteCreate(BaseModel):
    empresa_id: uuid.UUID
    fecha: date
    descripcion: str
    lineas: list[LineaCreate] = Field(min_length=1)


class LineaOut(BaseModel):
    id: uuid.UUID
    cuenta_id: uuid.UUID
    tercero_id: uuid.UUID | None
    debito: Decimal
    credito: Decimal
    descripcion: str | None

    class Config:
        from_attributes = True


class ComprobanteOut(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    numero: int | None
    fecha: date
    descripcion: str
    estado: EstadoComprobante
    comprobante_original_id: uuid.UUID | None
    lineas: list[LineaOut]

    class Config:
        from_attributes = True


# ---------- Libro mayor ----------
class MovimientoLibroMayor(BaseModel):
    fecha: date
    numero: int | None
    comprobante_id: uuid.UUID
    descripcion: str
    tercero: str | None
    debito: Decimal
    credito: Decimal
    saldo_acumulado: Decimal


# ---------- Exógena ----------
class ExogenaGenerarRequest(BaseModel):
    empresa_id: uuid.UUID
    anio_gravable: int
    umbral_uvt: Decimal = Decimal("0")


class ExogenaHistorialOut(BaseModel):
    id: uuid.UUID
    anio_gravable: int
    umbral_uvt: Decimal
    uvt_valor_usado: Decimal
    total_registros: int
    total_valor_bruto: Decimal
    generado_en: datetime

    class Config:
        from_attributes = True
