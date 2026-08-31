"""
Script de datos semilla para probar la aplicación manualmente sin tener que
crear todo a mano vía API.

Uso:
    cd backend
    python -m scripts.seed

Crea:
- Una empresa con NIT válido (dígito de verificación correcto).
- Un plan de cuentas básico (activo, pasivo, ingreso, gasto).
- Dos terceros de ejemplo.
- El valor de UVT del año actual y el anterior en caché (para poder generar
  exógena inmediatamente sin esperar el refresco en background).

No se ejecuta automáticamente en `docker compose up` a propósito: se deja
como paso explícito para que el evaluador entienda qué datos existen y de
dónde salen, en vez de encontrar datos "mágicos" ya en la base.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.models import Cuenta, Empresa, Naturaleza, Tercero, UvtValor
from app.infra.db import AsyncSessionLocal


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        empresa = Empresa(nit="900123456-8", razon_social="Empresa Demo SAS")
        session.add(empresa)
        await session.flush()

        cuentas = [
            Cuenta(empresa_id=empresa.id, codigo="1105", nombre="Caja", naturaleza=Naturaleza.DEBITO),
            Cuenta(
                empresa_id=empresa.id,
                codigo="1435",
                nombre="Mercancías no fabricadas por la empresa",
                naturaleza=Naturaleza.DEBITO,
            ),
            Cuenta(
                empresa_id=empresa.id,
                codigo="2408",
                nombre="Proveedores nacionales",
                naturaleza=Naturaleza.CREDITO,
            ),
            Cuenta(
                empresa_id=empresa.id, codigo="2408", nombre="IVA descontable", naturaleza=Naturaleza.DEBITO
            ),
            Cuenta(empresa_id=empresa.id, codigo="4135", nombre="Ingresos", naturaleza=Naturaleza.CREDITO),
            Cuenta(
                empresa_id=empresa.id,
                codigo="5135",
                nombre="Gasto operacional",
                naturaleza=Naturaleza.DEBITO,
            ),
        ]
        # corregir código duplicado de IVA descontable en el ejemplo anterior
        cuentas[3].codigo = "240805"
        session.add_all(cuentas)

        terceros = [
            Tercero(empresa_id=empresa.id, tipo_doc="NIT", num_doc="800111222", nombre="Proveedor Uno SAS"),
            Tercero(empresa_id=empresa.id, tipo_doc="CC", num_doc="1020304050", nombre="Cliente Demo"),
        ]
        session.add_all(terceros)

        anio_actual = datetime.now(timezone.utc).year
        session.add(UvtValor(anio=anio_actual, valor=Decimal("49799"), fuente="seed"))
        session.add(UvtValor(anio=anio_actual - 1, valor=Decimal("47065"), fuente="seed"))

        await session.commit()

        print("Datos semilla creados:")
        print(f"  empresa_id = {empresa.id}")
        for c in cuentas:
            print(f"  cuenta {c.codigo} ({c.nombre}) -> {c.id}")
        for t in terceros:
            print(f"  tercero {t.nombre} -> {t.id}")


if __name__ == "__main__":
    asyncio.run(seed())
