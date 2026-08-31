"use client";

import { useEffect, useMemo, useState } from "react";
import { api, Cuenta, LineaComprobante } from "@/lib/api";
import { SelectorEmpresa, useEmpresaSeleccionada } from "@/components/SelectorEmpresa";

type LineaForm = LineaComprobante & { key: string };

function nuevaLinea(): LineaForm {
  return { key: crypto.randomUUID(), cuenta_id: "", debito: "0", credito: "0" };
}

export default function ComprobantesPage() {
  const { empresaId, setEmpresaId } = useEmpresaSeleccionada();
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [descripcion, setDescripcion] = useState("");
  const [lineas, setLineas] = useState<LineaForm[]>([nuevaLinea(), nuevaLinea()]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!empresaId) return;
    api
      .listarCuentas(empresaId)
      .then(setCuentas)
      .catch((e) => setError(e.message));
  }, [empresaId]);

  const totalDebito = useMemo(
    () => lineas.reduce((acc, l) => acc + (parseFloat(l.debito) || 0), 0),
    [lineas]
  );
  const totalCredito = useMemo(
    () => lineas.reduce((acc, l) => acc + (parseFloat(l.credito) || 0), 0),
    [lineas]
  );
  const diferencia = totalDebito - totalCredito;
  const balanceado = Math.abs(diferencia) < 0.001;

  function actualizarLinea(key: string, cambios: Partial<LineaForm>) {
    setLineas((prev) => prev.map((l) => (l.key === key ? { ...l, ...cambios } : l)));
  }

  function agregarLinea() {
    setLineas((prev) => [...prev, nuevaLinea()]);
  }

  function eliminarLinea(key: string) {
    setLineas((prev) => (prev.length > 2 ? prev.filter((l) => l.key !== key) : prev));
  }

  async function guardarBorrador(contabilizarDespues: boolean) {
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
        const contabilizado = await api.contabilizar(comprobante.id);
        setMensaje(`Comprobante N.° ${contabilizado.numero} contabilizado`);
      } else {
        setMensaje("Comprobante guardado como borrador");
      }
      setDescripcion("");
      setLineas([nuevaLinea(), nuevaLinea()]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="stack-lg">
      <header className="page-header">
        <h1>Comprobantes</h1>
        <p className="page-lead">
          Registra un asiento contable. Debe quedar balanceado (total débitos = total créditos)
          antes de poder contabilizarlo.
        </p>
      </header>

      <SelectorEmpresa empresaId={empresaId} onChange={setEmpresaId} />

      {empresaId && (
        <section className="panel">
          <div className="form-row">
            <div className="field">
              <label>Fecha</label>
              <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </div>
            <div className="field field--grow">
              <label>Descripción</label>
              <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            </div>
          </div>

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
                      onChange={(e) => actualizarLinea(linea.key, { cuenta_id: e.target.value })}
                    >
                      <option value="">Seleccionar...</option>
                      {cuentas.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.codigo} · {c.nombre}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      placeholder="ID tercero"
                      className="mono"
                      value={linea.tercero_id ?? ""}
                      onChange={(e) => actualizarLinea(linea.key, { tercero_id: e.target.value || null })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="mono"
                      value={linea.debito}
                      onChange={(e) => actualizarLinea(linea.key, { debito: e.target.value, credito: "0" })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="mono"
                      value={linea.credito}
                      onChange={(e) => actualizarLinea(linea.key, { credito: e.target.value, debito: "0" })}
                    />
                  </td>
                  <td>
                    <input
                      value={linea.descripcion ?? ""}
                      onChange={(e) => actualizarLinea(linea.key, { descripcion: e.target.value })}
                    />
                  </td>
                  <td>
                    <button
                      className="btn btn--secondary"
                      onClick={() => eliminarLinea(linea.key)}
                      disabled={lineas.length <= 2}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <button className="btn btn--secondary" onClick={agregarLinea} style={{ marginTop: "0.75rem" }}>
            + Agregar línea
          </button>

          <dl className="balance">
            <div>
              <dt>Débitos</dt>
              <dd>{totalDebito.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Créditos</dt>
              <dd>{totalCredito.toFixed(2)}</dd>
            </div>
            <div className={balanceado ? "diff-ok" : "diff-bad"}>
              <dt>Diferencia</dt>
              <dd>
                {diferencia.toFixed(2)} {balanceado ? "· balanceado" : "· desbalanceado"}
              </dd>
            </div>
          </dl>

          {error && <div className="banner banner--error">{error}</div>}
          {mensaje && <div className="banner banner--ok">{mensaje}</div>}

          <div className="form-row" style={{ marginTop: "1.25rem", marginBottom: 0 }}>
            <button
              className="btn btn--secondary"
              disabled={guardando || !empresaId || !descripcion}
              onClick={() => guardarBorrador(false)}
            >
              Guardar como borrador
            </button>
            <button
              className="btn btn--primary"
              disabled={guardando || !empresaId || !descripcion || !balanceado}
              onClick={() => guardarBorrador(true)}
            >
              Guardar y contabilizar
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
