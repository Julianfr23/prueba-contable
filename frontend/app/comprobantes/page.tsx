"use client";

import { useEffect, useMemo, useState } from "react";
import { api, Comprobante, Cuenta, LineaComprobante } from "@/lib/api";
import {
SelectorEmpresa,
useEmpresaSeleccionada,
} from "@/components/SelectorEmpresa";

type LineaForm = LineaComprobante & { key: string };

function nuevaLinea(): LineaForm {
return {
key: crypto.randomUUID(),
cuenta_id: "",
debito: "0",
credito: "0",
};
}

function formatearMonto(valor: string) {
return Number(valor).toLocaleString("es-CO", {
minimumFractionDigits: 2,
maximumFractionDigits: 2,
});
}

function etiquetaEstado(estado: Comprobante["estado"]) {
switch (estado) {
case "contabilizado":
return "Contabilizado";
case "borrador":
return "Borrador";
case "reversado":
return "Reversado";
case "reversion":
return "Reversión";
default:
return estado;
}
}

export default function ComprobantesPage() {
const { empresaId, setEmpresaId } = useEmpresaSeleccionada();

const [cuentas, setCuentas] = useState<Cuenta[]>([]);
const [comprobantes, setComprobantes] = useState<Comprobante[]>([]);

const [fecha, setFecha] = useState(() =>
new Date().toISOString().slice(0, 10)
);

const [descripcion, setDescripcion] = useState("");

const [lineas, setLineas] = useState<LineaForm[]>([
nuevaLinea(),
nuevaLinea(),
]);

const [error, setError] = useState<string | null>(null);
const [mensaje, setMensaje] = useState<string | null>(null);

const [guardando, setGuardando] = useState(false);
const [cargandoComprobantes, setCargandoComprobantes] =
useState(false);

const [procesandoId, setProcesandoId] = useState<string | null>(
null
);

const [comprobanteExpandido, setComprobanteExpandido] =
useState<string | null>(null);

useEffect(() => {
if (!empresaId) {
setCuentas([]);
setComprobantes([]);
return;
}


setError(null);

api
  .listarCuentas(empresaId)
  .then(setCuentas)
  .catch((e) => setError(e.message));

cargarComprobantes(empresaId);


}, [empresaId]);

async function cargarComprobantes(id: string) {
setCargandoComprobantes(true);


try {
  const data = await api.listarComprobantes(id);
  setComprobantes(data);
} catch (e: any) {
  setError(e.message);
} finally {
  setCargandoComprobantes(false);
}


}

const totalDebito = useMemo(
() =>
lineas.reduce(
(acc, l) => acc + (parseFloat(l.debito) || 0),
0
),
[lineas]
);

const totalCredito = useMemo(
() =>
lineas.reduce(
(acc, l) => acc + (parseFloat(l.credito) || 0),
0
),
[lineas]
);

const diferencia = totalDebito - totalCredito;
const balanceado = Math.abs(diferencia) < 0.001;

function actualizarLinea(
key: string,
cambios: Partial<LineaForm>
) {
setLineas((prev) =>
prev.map((l) =>
l.key === key ? { ...l, ...cambios } : l
)
);
}

function agregarLinea() {
setLineas((prev) => [...prev, nuevaLinea()]);
}

function eliminarLinea(key: string) {
setLineas((prev) =>
prev.length > 2
? prev.filter((l) => l.key !== key)
: prev
);
}

async function guardarBorrador(
contabilizarDespues: boolean
) {
if (!empresaId) return;


setError(null);
setMensaje(null);
setGuardando(true);

try {
  const comprobante = await api.crearBorrador({
    empresa_id: empresaId,
    fecha,
    descripcion,
    lineas: lineas.map(({ key, ...resto }) => resto),
  });

  if (contabilizarDespues) {
    const contabilizado = await api.contabilizar(
      comprobante.id
    );

    setMensaje(
      `Comprobante N.° ${contabilizado.numero} contabilizado`
    );
  } else {
    setMensaje("Comprobante guardado como borrador");
  }

  setDescripcion("");
  setLineas([nuevaLinea(), nuevaLinea()]);

  await cargarComprobantes(empresaId);
} catch (e: any) {
  setError(e.message);
} finally {
  setGuardando(false);
}


}

async function contabilizarComprobante(
comprobanteId: string
) {
if (!empresaId) return;


setError(null);
setMensaje(null);
setProcesandoId(comprobanteId);

try {
  const comprobante = await api.contabilizar(
    comprobanteId
  );

  setMensaje(
    `Comprobante N.° ${comprobante.numero} contabilizado correctamente`
  );

  await cargarComprobantes(empresaId);
} catch (e: any) {
  setError(e.message);
} finally {
  setProcesandoId(null);
}


}

async function revertirComprobante(
comprobanteId: string
) {
if (!empresaId) return;


const motivo = window.prompt(
  "Ingrese el motivo de la reversión:"
);

if (motivo === null) {
  return;
}

const motivoLimpio = motivo.trim();

if (!motivoLimpio) {
  setError("Debe ingresar un motivo para realizar la reversión.");
  return;
}

setError(null);
setMensaje(null);
setProcesandoId(comprobanteId);

try {
  const comprobante = await api.revertir(
    comprobanteId,
    motivoLimpio
  );

  setMensaje(
    `Comprobante N.° ${comprobante.numero ?? "—"} revertido correctamente`
  );

  await cargarComprobantes(empresaId);
} catch (e: any) {
  setError(e.message);
} finally {
  setProcesandoId(null);
}

}

function obtenerCuenta(cuentaId: string) {
return cuentas.find(
(cuenta) => cuenta.id === cuentaId
);
}

function calcularTotales(comprobante: Comprobante) {
return comprobante.lineas.reduce(
(totales, linea) => {
totales.debito += Number(linea.debito);
totales.credito += Number(linea.credito);
return totales;
},
{ debito: 0, credito: 0 }
);
}

return ( <div className="stack-lg"> <header className="page-header"> <h1>Comprobantes</h1>

    <p className="page-lead">
      Registra asientos contables, consulta su estado y
      verifica sus movimientos.
    </p>
  </header>

  <SelectorEmpresa
    empresaId={empresaId}
    onChange={setEmpresaId}
  />

  {empresaId && (
    <>
      <section className="panel">
        <h2>Nuevo comprobante</h2>

        <div className="form-row">
          <div className="field">
            <label>Fecha</label>

            <input
              type="date"
              value={fecha}
              onChange={(e) =>
                setFecha(e.target.value)
              }
            />
          </div>

          <div className="field field--grow">
            <label>Descripción</label>

            <input
              value={descripcion}
              onChange={(e) =>
                setDescripcion(e.target.value)
              }
              placeholder="Ej. Compra de materiales"
            />
          </div>
        </div>
        <div style={{ width: "100%", overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Cuenta</th>
              <th>Tercero</th>
              <th>Débito</th>
              <th>Crédito</th>
              <th>Descripción</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {lineas.map((linea) => (
              <tr key={linea.key}>
                <td>
                  <select
                    value={linea.cuenta_id}
                    onChange={(e) =>
                      actualizarLinea(
                        linea.key,
                        {
                          cuenta_id:
                            e.target.value,
                        }
                      )
                    }
                  >
                    <option value="">
                      Seleccionar...
                    </option>

                    {cuentas.map((cuenta) => (
                      <option
                        key={cuenta.id}
                        value={cuenta.id}
                      >
                        {cuenta.codigo} ·{" "}
                        {cuenta.nombre}
                      </option>
                    ))}
                  </select>
                </td>

                <td>
                  <input
                    placeholder="ID tercero"
                    className="mono"
                    value={
                      linea.tercero_id ?? ""
                    }
                    onChange={(e) =>
                      actualizarLinea(
                        linea.key,
                        {
                          tercero_id:
                            e.target.value ||
                            null,
                        }
                      )
                    }
                  />
                </td>

                <td>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="mono"
                    value={linea.debito}
                    onChange={(e) =>
                      actualizarLinea(
                        linea.key,
                        {
                          debito:
                            e.target.value,
                          credito: "0",
                        }
                      )
                    }
                  />
                </td>

                <td>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="mono"
                    value={linea.credito}
                    onChange={(e) =>
                      actualizarLinea(
                        linea.key,
                        {
                          credito:
                            e.target.value,
                          debito: "0",
                        }
                      )
                    }
                  />
                </td>

                <td>
                  <input
                    value={
                      linea.descripcion ?? ""
                    }
                    onChange={(e) =>
                      actualizarLinea(
                        linea.key,
                        {
                          descripcion:
                            e.target.value,
                        }
                      )
                    }
                  />
                </td>

                <td>
                  <button
                    className="btn btn--secondary"
                    onClick={() =>
                      eliminarLinea(
                        linea.key
                      )
                    }
                    disabled={
                      lineas.length <= 2
                    }
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <button
          className="btn btn--secondary"
          onClick={agregarLinea}
          style={{ marginTop: "0.75rem" }}
        >
          + Agregar línea
        </button>

        <dl className="balance">
          <div>
            <dt>Débitos</dt>
            <dd>
              {totalDebito.toFixed(2)}
            </dd>
          </div>

          <div>
            <dt>Créditos</dt>
            <dd>
              {totalCredito.toFixed(2)}
            </dd>
          </div>

          <div
            className={
              balanceado
                ? "diff-ok"
                : "diff-bad"
            }
          >
            <dt>Diferencia</dt>

            <dd>
              {diferencia.toFixed(2)}{" "}
              {balanceado
                ? "· balanceado"
                : "· desbalanceado"}
            </dd>
          </div>
        </dl>

        {error && (
          <div className="banner banner--error">
            {error}
          </div>
        )}

        {mensaje && (
          <div className="banner banner--ok">
            {mensaje}
          </div>
        )}

        <div
          className="form-row"
          style={{
            marginTop: "1.25rem",
            marginBottom: 0,
          }}
        >
          <button
            className="btn btn--secondary"
            disabled={
              guardando ||
              !empresaId ||
              !descripcion
            }
            onClick={() =>
              guardarBorrador(false)
            }
          >
            {guardando
              ? "Guardando..."
              : "Guardar como borrador"}
          </button>

          <button
            className="btn btn--primary"
            disabled={
              guardando ||
              !empresaId ||
              !descripcion ||
              !balanceado
            }
            onClick={() =>
              guardarBorrador(true)
            }
          >
            {guardando
              ? "Guardando..."
              : "Guardar y contabilizar"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div
          className="form-row"
          style={{
            justifyContent:
              "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h2>
              Listado de comprobantes
            </h2>

            <p className="page-lead">
              Consulta los comprobantes
              registrados para la empresa
              seleccionada.
            </p>
          </div>

          <button
            className="btn btn--secondary"
            onClick={() =>
              cargarComprobantes(
                empresaId
              )
            }
            disabled={
              cargandoComprobantes
            }
          >
            {cargandoComprobantes
              ? "Actualizando..."
              : "Actualizar"}
          </button>
        </div>

        {cargandoComprobantes ? (
          <p>
            Cargando comprobantes...
          </p>
        ) : comprobantes.length === 0 ? (
          <div className="banner">
            No hay comprobantes registrados
            para esta empresa.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>N.º</th>
                <th>Fecha</th>
                <th>Descripción</th>
                <th>Estado</th>
                <th>Débito</th>
                <th>Crédito</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              {comprobantes.map(
                (comprobante) => {
                  const totales =
                    calcularTotales(
                      comprobante
                    );

                  const expandido =
                    comprobanteExpandido ===
                    comprobante.id;

                  const procesando =
                    procesandoId ===
                    comprobante.id;

                  return (
                    <tr
                      key={
                        comprobante.id
                      }
                    >
                      <td className="mono">
                        {comprobante.numero ??
                          "—"}
                      </td>

                      <td>
                        {comprobante.fecha}
                      </td>

                      <td>
                        {
                          comprobante.descripcion
                        }
                      </td>

                      <td>
                        {
                          etiquetaEstado(
                            comprobante.estado
                          )
                        }
                      </td>

                      <td className="mono">
                        {formatearMonto(
                          totales.debito.toString()
                        )}
                      </td>

                      <td className="mono">
                        {formatearMonto(
                          totales.credito.toString()
                        )}
                      </td>

                      <td>
                        <div
                          style={{
                            display:
                              "flex",
                            gap:
                              "0.5rem",
                            flexWrap:
                              "wrap",
                          }}
                        >
                          <button
                            className="btn btn--secondary"
                            onClick={() =>
                              setComprobanteExpandido(
                                expandido
                                  ? null
                                  : comprobante.id
                              )
                            }
                          >
                            {expandido
                              ? "Ocultar"
                              : "Ver detalle"}
                          </button>

                          {comprobante.estado ===
                            "borrador" && (
                            <button
                              className="btn btn--primary"
                              disabled={
                                procesando
                              }
                              onClick={() =>
                                contabilizarComprobante(
                                  comprobante.id
                                )
                              }
                            >
                              {procesando
                                ? "Contabilizando..."
                                : "Contabilizar"}
                            </button>
                          )}

                          {comprobante.estado ===
                            "contabilizado" && (
                            <button
                              className="btn btn--secondary"
                              disabled={
                                procesando
                              }
                              onClick={() =>
                                revertirComprobante(
                                  comprobante.id
                                )
                              }
                            >
                              {procesando
                                ? "Revirtiendo..."
                                : "Revertir"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                }
              )}
            </tbody>
          </table>
        )}

        {comprobantes.map(
          (comprobante) => {
            if (
              comprobanteExpandido !==
              comprobante.id
            ) {
              return null;
            }

            return (
              <div
                key={`detalle-${comprobante.id}`}
                className="panel"
                style={{
                  marginTop: "1rem",
                  background:
                    "var(--surface-soft)",
                }}
              >
                <h3>
                  Detalle del comprobante{" "}
                  {comprobante.numero
                    ? `N.° ${comprobante.numero}`
                    : "(Borrador)"}
                </h3>

                <p>
                  <strong>
                    Estado:
                  </strong>{" "}
                  {etiquetaEstado(
                    comprobante.estado
                  )}
                </p>

                <table className="table">
                  <thead>
                    <tr>
                      <th>Cuenta</th>
                      <th>Tercero</th>
                      <th>Débito</th>
                      <th>Crédito</th>
                      <th>
                        Descripción
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {comprobante.lineas.map(
                      (linea) => {
                        const cuenta =
                          obtenerCuenta(
                            linea.cuenta_id
                          );

                        return (
                          <tr
                            key={
                              linea.id
                            }
                          >
                            <td>
                              {cuenta
                                ? `${cuenta.codigo} · ${cuenta.nombre}`
                                : linea.cuenta_id}
                            </td>

                            <td className="mono">
                              {linea.tercero_id ??
                                "—"}
                            </td>

                            <td className="mono">
                              {formatearMonto(
                                linea.debito
                              )}
                            </td>

                            <td className="mono">
                              {formatearMonto(
                                linea.credito
                              )}
                            </td>

                            <td>
                              {linea.descripcion ??
                                "—"}
                            </td>
                          </tr>
                        );
                      }
                    )}
                  </tbody>
                </table>
              </div>
            );
          }
        )}
      </section>
    </>
  )}
</div>

);
}
