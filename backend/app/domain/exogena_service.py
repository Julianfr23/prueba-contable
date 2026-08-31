from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Comprobante,
    Empresa,
    EstadoComprobante,
    ExogenaGeneracion,
    LineaContable,
    Tercero,
)
from app.domain.validaciones import ReglaContableError, validar_nit_digito_verificacion
from app.infra.uvt_provider import disparar_actualizacion_en_background, obtener_uvt_cacheado

logger = logging.getLogger("exogena_service")

"""
Alcance simplificado (documentado también en el README):
- Se agrupan los movimientos CONTABILIZADOS del año gravable por tercero y
  por "concepto" (aquí simplificado como el código de cuenta usado en la
  línea; un mapeo cuenta->concepto DIAN real queda fuera de alcance).
- `valorRetencion` se deja en 0 porque el modelo actual no captura
  retenciones como un concepto separado; se documenta como pendiente.
- El umbral en UVT se convierte a pesos usando el valor de UVT cacheado
  para el año gravable. Si no hay valor cacheado, se dispara una
  actualización en background y se informa al usuario que reintente
  (no se bloquea la request esperando al proveedor externo).
"""


async def generar_exogena(
    session: AsyncSession,
    empresa_id: uuid.UUID,
    anio_gravable: int,
    umbral_uvt: Decimal,
) -> ExogenaGeneracion:
    empresa = await session.get(Empresa, empresa_id)
    if empresa is None:
        raise ReglaContableError("Empresa no encontrada")

    # --- Validación del NIT del informante ---
    nit_completo = empresa.nit
    if "-" in nit_completo:
        nit_base, dv_str = nit_completo.split("-", 1)
        dv = int(dv_str)
    else:
        raise ReglaContableError(
            "El NIT de la empresa debe incluir el dígito de verificación, formato '900123456-7'"
        )
    if not validar_nit_digito_verificacion(nit_base, dv):
        raise ReglaContableError(f"El dígito de verificación del NIT {nit_completo} es inválido")

    # --- Valor de la UVT (desde caché, nunca bloqueando en el proveedor externo) ---
    uvt = await obtener_uvt_cacheado(session, anio_gravable)
    if uvt is None:
        disparar_actualizacion_en_background(anio_gravable)
        raise ReglaContableError(
            f"El valor de la UVT para {anio_gravable} aún no está disponible en caché; "
            "se disparó una actualización en background, intenta de nuevo en unos segundos"
        )

    umbral_pesos = umbral_uvt * uvt.valor

    # --- Movimientos del año gravable, agrupados por tercero + concepto (cuenta) ---
    stmt = (
        select(LineaContable, Tercero, Comprobante)
        .join(Comprobante, LineaContable.comprobante_id == Comprobante.id)
        .join(Tercero, LineaContable.tercero_id == Tercero.id)
        .where(
            Comprobante.empresa_id == empresa_id,
            Comprobante.estado.in_([EstadoComprobante.CONTABILIZADO, EstadoComprobante.REVERSION]),
        )
    )
    result = await session.execute(stmt)
    rows = result.all()
    rows = [r for r in rows if r[2].fecha.year == anio_gravable]

    agrupado: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"tercero": None, "concepto": None, "valor_bruto": Decimal("0")}
    )
    for linea, tercero, comprobante in rows:
        clave = (str(tercero.id), str(linea.cuenta_id))
        agrupado[clave]["tercero"] = tercero
        agrupado[clave]["concepto"] = str(linea.cuenta_id)
        agrupado[clave]["valor_bruto"] += linea.debito + linea.credito

    # --- Aplicar umbral, con trazabilidad de exclusiones ---
    incluidos = []
    excluidos_log = []
    totales_por_tercero: dict[str, Decimal] = defaultdict(Decimal)
    for (tercero_id, _concepto), datos in agrupado.items():
        totales_por_tercero[tercero_id] += datos["valor_bruto"]

    for clave, datos in agrupado.items():
        tercero_id = clave[0]
        if totales_por_tercero[tercero_id] < umbral_pesos:
            excluidos_log.append(
                f"Tercero {datos['tercero'].nombre} excluido: total "
                f"{totales_por_tercero[tercero_id]} < umbral {umbral_pesos}"
            )
            continue
        incluidos.append(datos)

    for linea_log in excluidos_log:
        logger.info("Exógena %s: %s", anio_gravable, linea_log)

    # --- Construcción del XML ---
    root = Element(
        "InformacionExogena",
        {"version": "1.0"},
    )
    SubElement(
        root,
        "Informante",
        {
            "nit": nit_base,
            "dv": str(dv),
            "razonSocial": empresa.razon_social,
            "anioGravable": str(anio_gravable),
        },
    )
    registros_el = SubElement(root, "Registros")
    total_valor_bruto = Decimal("0")
    for datos in incluidos:
        tercero: Tercero = datos["tercero"]
        SubElement(
            registros_el,
            "Registro",
            {
                "tipoDoc": tercero.tipo_doc,
                "numDoc": tercero.num_doc,
                "nombre": tercero.nombre,
                "concepto": datos["concepto"],
                "valorBruto": str(datos["valor_bruto"]),
                "valorRetencion": "0",
            },
        )
        total_valor_bruto += datos["valor_bruto"]

    SubElement(
        root,
        "Totales",
        {
            "registros": str(len(incluidos)),
            "totalValorBruto": str(total_valor_bruto),
            "totalRetencion": "0",
        },
    )

    xml_str = minidom.parseString(tostring(root, encoding="unicode")).toprettyxml(indent="  ")

    generacion = ExogenaGeneracion(
        empresa_id=empresa_id,
        anio_gravable=anio_gravable,
        umbral_uvt=umbral_uvt,
        uvt_valor_usado=uvt.valor,
        xml_contenido=xml_str,
        total_registros=len(incluidos),
        total_valor_bruto=total_valor_bruto,
    )
    session.add(generacion)
    await session.commit()
    await session.refresh(generacion)
    return generacion
