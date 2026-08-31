"""
Reglas de negocio puras (sin dependencias de DB) para poder testearlas de
forma aislada y rápida. La capa de servicio (comprobante_service.py) las
invoca después de cargar el estado necesario desde la base de datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class ReglaContableError(Exception):
    """Error de negocio: la causa exacta va en el mensaje (se expone al usuario)."""


@dataclass
class LineaValidable:
    cuenta_id: str
    cuenta_activa: bool
    debito: Decimal
    credito: Decimal


def validar_minimo_dos_lineas(lineas: list) -> None:
    if len(lineas) < 2:
        raise ReglaContableError("El comprobante debe tener al menos dos líneas contables")


def validar_valores_positivos_y_precision(lineas: list[LineaValidable]) -> None:
    for linea in lineas:
        for valor in (linea.debito, linea.credito):
            if valor < 0:
                raise ReglaContableError("Los valores de las líneas no pueden ser negativos")
            # exponent > -2 significa más de 2 decimales, ej Decimal('1.005') -> exponent -3
            if valor.as_tuple().exponent < -2:
                raise ReglaContableError(
                    "Los valores monetarios no pueden tener más de 2 decimales"
                )


def validar_no_debito_y_credito_simultaneo(lineas: list[LineaValidable]) -> None:
    for linea in lineas:
        if linea.debito > 0 and linea.credito > 0:
            raise ReglaContableError(
                "Una línea no puede tener débito y crédito simultáneamente"
            )


def validar_partida_doble(lineas: list[LineaValidable]) -> None:
    total_debito = sum((l.debito for l in lineas), Decimal("0"))
    total_credito = sum((l.credito for l in lineas), Decimal("0"))
    if total_debito != total_credito:
        raise ReglaContableError(
            f"El comprobante está desbalanceado: débitos={total_debito} créditos={total_credito}"
        )


def validar_cuentas_activas(lineas: list[LineaValidable]) -> None:
    inactivas = {l.cuenta_id for l in lineas if not l.cuenta_activa}
    if inactivas:
        raise ReglaContableError(
            f"Las siguientes cuentas están inactivas y no pueden usarse: {', '.join(inactivas)}"
        )


def validar_periodo_abierto(periodo_estado: str) -> None:
    if periodo_estado != "abierto":
        raise ReglaContableError(
            "El período contable está cerrado; no se pueden contabilizar comprobantes en él"
        )


def validar_comprobante_para_contabilizar(
    lineas: list[LineaValidable], periodo_estado: str
) -> None:
    """Orquesta todas las validaciones de negocio antes de contabilizar."""
    validar_minimo_dos_lineas(lineas)
    validar_valores_positivos_y_precision(lineas)
    validar_no_debito_y_credito_simultaneo(lineas)
    validar_partida_doble(lineas)
    validar_cuentas_activas(lineas)
    validar_periodo_abierto(periodo_estado)


def validar_nit_digito_verificacion(nit: str, dv_informado: int) -> bool:
    """
    Implementación del algoritmo oficial de la DIAN (Colombia) para el
    dígito de verificación del NIT, usado para validar el NIT del
    informante antes de incluirlo en el archivo de exógena.
    """
    pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_limpio = nit.strip().replace("-", "").replace(".", "")
    if not nit_limpio.isdigit():
        raise ReglaContableError("El NIT solo debe contener dígitos")

    digitos = [int(d) for d in reversed(nit_limpio)]
    total = sum(d * pesos[i] for i, d in enumerate(digitos) if i < len(pesos))
    residuo = total % 11
    dv_calculado = residuo if residuo in (0, 1) else 11 - residuo
    return dv_calculado == dv_informado
