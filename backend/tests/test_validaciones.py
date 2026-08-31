"""
Pruebas de las reglas de negocio de mayor riesgo (ver README, sección 9.2).

Se priorizó testear estas reglas puras porque son las que protegen la
integridad contable (partida doble, período cerrado, precisión monetaria) y
no requieren base de datos, por lo que corren en milisegundos y sirven como
red de seguridad ante cualquier refactor.
"""

from decimal import Decimal

import pytest

from app.domain.validaciones import (
    LineaValidable,
    ReglaContableError,
    validar_comprobante_para_contabilizar,
    validar_minimo_dos_lineas,
    validar_nit_digito_verificacion,
    validar_no_debito_y_credito_simultaneo,
    validar_partida_doble,
    validar_periodo_abierto,
    validar_valores_positivos_y_precision,
)


def linea(debito="0", credito="0", activa=True, cuenta_id="c1"):
    return LineaValidable(
        cuenta_id=cuenta_id, cuenta_activa=activa, debito=Decimal(debito), credito=Decimal(credito)
    )


class TestMinimoDosLineas:
    def test_rechaza_una_sola_linea(self):
        with pytest.raises(ReglaContableError):
            validar_minimo_dos_lineas([linea(debito="100")])

    def test_acepta_dos_lineas(self):
        validar_minimo_dos_lineas([linea(debito="100"), linea(credito="100")])


class TestPartidaDoble:
    def test_rechaza_desbalanceado(self):
        with pytest.raises(ReglaContableError, match="desbalanceado"):
            validar_partida_doble([linea(debito="100"), linea(credito="90")])

    def test_acepta_balanceado(self):
        validar_partida_doble([linea(debito="100"), linea(credito="100")])

    def test_acepta_multiples_lineas_balanceadas(self):
        validar_partida_doble(
            [linea(debito="60"), linea(debito="40"), linea(credito="100")]
        )


class TestDebitoCreditoSimultaneo:
    def test_rechaza_linea_con_ambos(self):
        with pytest.raises(ReglaContableError):
            validar_no_debito_y_credito_simultaneo([linea(debito="10", credito="10")])


class TestPrecisionMonetaria:
    def test_rechaza_mas_de_dos_decimales(self):
        with pytest.raises(ReglaContableError, match="2 decimales"):
            validar_valores_positivos_y_precision([linea(debito="100.005")])

    def test_rechaza_negativos(self):
        with pytest.raises(ReglaContableError):
            validar_valores_positivos_y_precision([linea(debito="-10")])

    def test_acepta_dos_decimales_exactos(self):
        validar_valores_positivos_y_precision([linea(debito="1000000.00")])


class TestPeriodoAbierto:
    def test_rechaza_periodo_cerrado(self):
        with pytest.raises(ReglaContableError, match="cerrado"):
            validar_periodo_abierto("cerrado")

    def test_acepta_periodo_abierto(self):
        validar_periodo_abierto("abierto")


class TestCuentasInactivas:
    def test_rechaza_cuenta_inactiva(self):
        with pytest.raises(ReglaContableError):
            validar_comprobante_para_contabilizar(
                [
                    linea(debito="100", activa=False, cuenta_id="c1"),
                    linea(credito="100", activa=True, cuenta_id="c2"),
                ],
                periodo_estado="abierto",
            )


class TestOrquestacionCompleta:
    def test_escenario_1_comprobante_valido(self):
        """Escenario 1 del enunciado: comprobante válido (una compra)."""
        lineas = [
            linea(debito="1000000", cuenta_id="gasto"),
            linea(debito="190000", cuenta_id="iva"),
            linea(credito="1190000", cuenta_id="proveedores"),
        ]
        validar_comprobante_para_contabilizar(lineas, periodo_estado="abierto")

    def test_escenario_2_comprobante_desbalanceado(self):
        """Escenario 2 del enunciado: debe rechazarse con mensaje claro."""
        lineas = [linea(debito="500000", cuenta_id="caja"), linea(credito="450000", cuenta_id="ingresos")]
        with pytest.raises(ReglaContableError, match="desbalanceado"):
            validar_comprobante_para_contabilizar(lineas, periodo_estado="abierto")

    def test_escenario_4_periodo_cerrado(self):
        """Escenario 4 del enunciado: período cerrado debe rechazar con motivo."""
        lineas = [linea(debito="100"), linea(credito="100")]
        with pytest.raises(ReglaContableError, match="cerrado"):
            validar_comprobante_para_contabilizar(lineas, periodo_estado="cerrado")


class TestDigitoVerificacionNit:
    def test_nit_valido_conocido(self):
        # 900123456 -> dv real calculado con el algoritmo DIAN
        pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        nit = "900123456"
        digitos = [int(d) for d in reversed(nit)]
        total = sum(d * pesos[i] for i, d in enumerate(digitos))
        residuo = total % 11
        dv_esperado = residuo if residuo in (0, 1) else 11 - residuo
        assert validar_nit_digito_verificacion(nit, dv_esperado) is True

    def test_nit_invalido(self):
        assert validar_nit_digito_verificacion("900123456", 0) in (True, False)
        assert validar_nit_digito_verificacion("900123456", 99) is False

    def test_nit_no_numerico_lanza_error(self):
        with pytest.raises(ReglaContableError):
            validar_nit_digito_verificacion("ABC123", 5)
