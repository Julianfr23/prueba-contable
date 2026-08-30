# Prueba técnica — Motor contable

Stack: **FastAPI (Python)** · **Next.js/React (TypeScript)** · **PostgreSQL**

## 1. Cómo levantar el proyecto en local

### Opción A — Docker Compose (recomendada)

```bash
docker compose up --build
```

Esto levanta PostgreSQL, corre las migraciones automáticamente y expone:
- Backend: http://localhost:8000 (docs interactivas en `/docs`)
- Frontend: http://localhost:3000

### Opción B — Manual

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajusta DATABASE_URL si tu Postgres no usa las credenciales por defecto
# Levanta un Postgres local, por ejemplo:
#   docker run -e POSTGRES_USER=contable -e POSTGRES_PASSWORD=contable -e POSTGRES_DB=contable -p 5432:5432 postgres:16
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

### Datos iniciales

Hay un script de datos semilla para no tener que crear todo a mano:

```bash
cd backend
python -m scripts.seed
```

Esto crea una empresa con NIT válido, un plan de cuentas básico, dos terceros de ejemplo, y precarga el valor de UVT del año actual y el anterior (para poder generar exógena de inmediato sin esperar el refresco en background). El script imprime los IDs generados, incluido el `empresa_id` que debes pegar en las 3 vistas del frontend.

Alternativamente, de forma manual vía la API:

1. Crear una empresa: `POST /api/empresas` con `{"nit": "900123456-8", "razon_social": "Mi Empresa SAS"}`
   (el NIT debe incluir el dígito de verificación real, se valida con el algoritmo de la DIAN).
2. Crear cuentas del plan de cuentas: `POST /api/empresas/{empresa_id}/cuentas`.
3. Copiar el `empresa_id` en cualquiera de las 3 vistas del frontend.

## 2. Migraciones

```bash
cd backend
alembic upgrade head        # aplicar
alembic downgrade -1        # revertir la última
alembic revision --autogenerate -m "descripcion"   # generar una nueva a partir de cambios en los modelos
```

## 3. Pruebas

```bash
cd backend
pytest -v
```

Se priorizaron pruebas unitarias **puras** (sin base de datos) sobre las reglas de negocio de mayor riesgo: partida doble, mínimo de líneas, no débito/crédito simultáneo, precisión monetaria (rechazo de más de 2 decimales), período cerrado, cuentas inactivas y el dígito de verificación del NIT. No se buscó cobertura exhaustiva de cada línea; se buscó proteger específicamente las reglas que, si fallan, corrompen la integridad contable. Quedan como pendiente pruebas de integración contra una base de datos real (ver sección 6) para cubrir la numeración concurrente y la reversión de extremo a extremo.

## 4. Decisiones de diseño relevantes

- **Precisión monetaria**: todos los valores usan `Decimal` en Python y `Numeric(18,2)` en PostgreSQL en toda la pila (dominio, DB, validación de entrada en Pydantic). Nunca `float`. Además se valida explícitamente que ningún valor tenga más de 2 decimales antes de contabilizar.
- **Plan de cuentas**: tabla plana con `codigo` de tipo string; la jerarquía (grupos, subgrupos) se deriva por prefijos de código en lugar de una tabla de árbol materializada. Es suficiente para el alcance pedido y evita complejidad de mantenimiento de una estructura jerárquica explícita.
- **Numeración de comprobantes bajo concurrencia**: se usa una tabla `correlativos` (un contador por empresa) con `SELECT ... FOR UPDATE` dentro de la misma transacción que contabiliza. Esto serializa el incremento y evita números duplicados cuando dos requests contabilizan simultáneamente sobre la misma empresa (Escenario 6 del enunciado). Es una solución simple, adecuada al volumen esperado; para alto throughput se evaluaría una secuencia nativa de PostgreSQL particionada por empresa.
- **Reversión de comprobantes**: se implementa como un **nuevo comprobante** que invierte las líneas del original (débito↔crédito), enlazado por `comprobante_original_id`. El original se marca `REVERSADO` pero nunca se edita ni se borra. Esto preserva la trazabilidad completa: el libro mayor muestra ambos movimientos como hechos históricos reales, igual que en un libro contable físico.
- **Protección de comprobantes contabilizados**: se valida a nivel de servicio (`comprobante_service.py`) que solo se puedan contabilizar comprobantes en estado `borrador`, y que la reversión solo aplique sobre `contabilizado`. No se agregó un trigger de base de datos adicional para no duplicar la lógica de negocio en dos capas; se documenta como mejora si distintos clientes de la DB pudieran escribir directamente.
- **Libro mayor — saldo acumulado**: se calcula **en tiempo real** a partir de los movimientos (no hay saldos materializados). Prioriza consistencia sobre rendimiento: el saldo siempre refleja el estado real, sin riesgo de desincronización tras una reversión. El trade-off es el costo de la consulta con volúmenes muy grandes; la mitigación (snapshots por cierre de período) queda documentada en el código (`libro_mayor_service.py`) y como pendiente.
- **Integración externa de UVT**: la actualización del valor de la UVT corre en una tarea de background (`asyncio` en el ciclo de vida de la app, con refresco periódico configurable) y **nunca dentro del ciclo de una request HTTP**. Los endpoints leen un caché local (`uvt_valores`). Si falta el valor de un año, se dispara una actualización en background y se le informa al usuario que reintente, en vez de bloquear la petición. Incluye reintentos con backoff exponencial y una tabla de traza (`uvt_actualizacion_log`) de cada intento. El proveedor por defecto es **simulado** (valores de referencia embebidos) para que la prueba sea reproducible sin depender de la disponibilidad de una fuente externa real; se dejó también una implementación HTTP genérica (`UvtProviderHttp`) lista para apuntar a una fuente real vía configuración.
- **Exógena simplificada**: se agrupan movimientos contabilizados por tercero y por cuenta (usada aquí como proxy simplificado de "concepto"; un mapeo cuenta→concepto DIAN real no se implementó, ver Pendientes). El NIT del informante se valida con el algoritmo oficial de dígito de verificación antes de generar el archivo. El umbral en UVT se convierte a pesos con el valor cacheado del año gravable; los terceros excluidos por no superar el umbral quedan registrados en el log de la aplicación. Cada generación se persiste completa (incluyendo el XML) para permitir re-descarga sin recalcular.
- **Separación de responsabilidades**: `app/domain` contiene modelos, reglas de negocio puras y servicios (sin conocer FastAPI); `app/api` expone los servicios vía HTTP y traduce errores de negocio a códigos HTTP; `app/infra` contiene detalles de infraestructura (DB, proveedor externo). Las reglas de negocio críticas (`validaciones.py`) no dependen de SQLAlchemy ni de FastAPI, lo que permite testearlas de forma aislada y rápida.

## 5. Limitaciones conocidas

- No hay autenticación ni autorización (ver extensión opcional no implementada).
- El frontend usa `localStorage` solo para recordar el último `empresa_id` usado, como conveniencia; no hay selector de empresa con búsqueda ni gestión de terceros desde la UI (se crean vía API).
- La migración inicial de Alembic fue escrita a mano (reflejando los modelos) en lugar de generarse con `--autogenerate` contra una base real, porque este entorno no tuvo acceso a una instancia de PostgreSQL en el momento de desarrollo. Se recomienda correr `alembic upgrade head` contra una base limpia como primera verificación.
- Las pruebas automatizadas cubren la capa de reglas de negocio puras; no incluyen pruebas de integración end-to-end (API + DB) por límite de tiempo.
- El agrupamiento de exógena usa la cuenta como proxy de "concepto"; no implementa el catálogo real de conceptos DIAN.

## 6. Pendientes (qué faltó y cómo lo abordaría)

- **Pruebas de integración**: levantar un contenedor de Postgres efímero (ej. `testcontainers`) para probar `comprobante_service.contabilizar` bajo concurrencia real (dos tareas asyncio contabilizando simultáneamente) y la reversión de extremo a extremo contra la base de datos.
- **Reapertura de período** (mencionada en el enunciado, no obligatoria): la implementaría como una operación explícita y auditada — `POST /periodos/{id}/reabrir` — que exige un motivo, registra quién y cuándo la solicitó, y que además invalide/marque para revisión cualquier reporte de exógena ya generado que dependiera de ese período, ya que los datos subyacentes podrían cambiar.
- **Catálogo de conceptos DIAN real** para la exógena, en lugar del proxy por cuenta.
- **Autenticación JWT** (listada como extensión opcional, no implementada en esta entrega por tiempo — se priorizó el motor contable).
- **Jerarquía real del plan de cuentas** si se necesitan operaciones como "saldo consolidado de todas las subcuentas".

## 7. Extensión opcional elegida

Se implementaron dos extensiones pequeñas pero de alto valor percibido para llevar esto a un entorno real:

1. **Docker Compose** que levanta base de datos, backend y frontend con un solo comando — reduce fricción para que cualquiera (incluido el evaluador) pueda correr el proyecto sin configurar nada manualmente.
2. **Pipeline de CI básico en GitHub Actions** (`.github/workflows/ci.yml`) que corre las pruebas unitarias en cada push/PR — protege contra regresiones en las reglas de negocio desde el primer commit.

Se priorizaron estas dos sobre, por ejemplo, autenticación JWT, porque impactan directamente la confiabilidad y la facilidad de evaluación del resto del ejercicio, que es lo que más se está midiendo en esta prueba.

## 8. ¿Qué cambiarías para llevar esta solución a producción?

- Reemplazar el proveedor simulado de UVT por la fuente oficial real, con monitoreo/alertas si las actualizaciones fallan repetidamente (hoy solo quedan en un log de tabla).
- Agregar autenticación y autorización (JWT + roles: quién puede contabilizar, revertir o cerrar períodos — hoy cualquiera con acceso a la API puede hacer todo).
- Mover el cálculo de saldo del libro mayor a un esquema híbrido (snapshot por cierre + movimientos posteriores) si el volumen de movimientos por cuenta crece significativamente.
- Restringir `CORS` a los orígenes reales del frontend (hoy está abierto con `*` para facilitar la evaluación local).
- Agregar índices adicionales según los patrones de consulta reales observados en producción, y métricas/observabilidad (logs estructurados, tracing) sobre las operaciones críticas (contabilizar, revertir, generar exógena).
- Endurecer el manejo de errores parciales con pruebas de fallos inyectados (ej. simular una caída de conexión a mitad de la contabilización) para verificar que las transacciones realmente revierten por completo.
- Formalizar contratos de API con versionado (`/api/v1/...`) antes de tener consumidores externos.

## Estructura del repositorio

```
backend/    FastAPI, SQLAlchemy, Alembic, pruebas
frontend/   Next.js (App Router) con las 3 vistas requeridas
docker-compose.yml
.github/workflows/ci.yml
```
