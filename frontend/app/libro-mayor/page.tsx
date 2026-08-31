"use client";

import { useEffect, useState } from "react";
import { api, Cuenta, MovimientoLibroMayor } from "@/lib/api";
import { SelectorEmpresa, useEmpresaSeleccionada } from "@/components/SelectorEmpresa";

type Estado = "vacio" | "cargando" | "listo" | "error";

export default function LibroMayorPage() {
  const { empresaId, setEmpresaId } = useEmpresaSeleccionada();
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [cuentaId, setCuentaId] = useState("");
  const [fechaInicio, setFechaInicio] = useState(() => `${new Date().getFullYear()}-01-01`);
  const [fechaFin, setFechaFin] = useState(() => new Date().toISOString().slice(0, 10));
  const [movimientos, setMovimientos] = useState<MovimientoLibroMayor[]>([]);
  const [estado, setEstado] = useState<Estado>("vacio");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!empresaId) return;
    api.listarCuentas(empresaId).then(setCuentas).catch((e) => setError(e.message));
  }, [empresaId]);

  async function consultar() {
    setEstado("cargando");
    setError(null);
    try {
      const data = await api.libroMayor({
        empresa_id: empresaId,
        cuenta_id: cuentaId,
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
      });
      setMovimientos(data);
      setEstado("listo");
    } catch (e: any) {
      setError(e.message);
      setEstado("error");
    }
  }

  const cuentaSeleccionada = cuentas.find((c) => c.id === cuentaId);
  const saldoFinal = movimientos.length > 0 ? movimientos[movimientos.length - 1].saldo_acumulado : null;

  return (
    <div className="stack-lg">
      <header className="page-header">
        <h1>Libro mayor</h1>
        <p className="page-lead">Consulta el movimiento cronológico y el saldo acumulado de una cuenta.</p>
      </header>

      <SelectorEmpresa empresaId={empresaId} onChange={setEmpresaId} />

      {empresaId && (
        <section className="panel">
          <div className="form-row" style={{ marginBottom: "1.5rem" }}>
            <div className="field field--grow">
              <label>Cuenta</label>
              <select value={cuentaId} onChange={(e) => setCuentaId(e.target.value)}>
                <option value="">Seleccionar...</option>
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.codigo} · {c.nombre}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Desde</label>
              <input type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </div>
            <div className="field">
              <label>Hasta</label>
              <input type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
            </div>
            <button className="btn btn--primary" onClick={consultar} disabled={!cuentaId}>
              Consultar
            </button>
          </div>

          {estado === "vacio" && (
            <p className="empty-hint">Selecciona una cuenta y un rango de fechas para ver sus movimientos.</p>
          )}
          {estado === "cargando" && <p className="empty-hint">Cargando movimientos...</p>}
          {estado === "error" && <div className="banner banner--error">{error}</div>}
          {estado === "listo" && movimientos.length === 0 && (
            <p className="empty-hint">No hay movimientos contabilizados para los filtros seleccionados.</p>
          )}

          {estado === "listo" && movimientos.length > 0 && (
            <>
              <table className="table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>N.°</th>
                    <th>Descripción</th>
                    <th>Tercero</th>
                    <th style={{ textAlign: "right" }}>Débito</th>
                    <th style={{ textAlign: "right" }}>Crédito</th>
                    <th style={{ textAlign: "right" }}>Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {movimientos.map((m, i) => (
                    <tr key={i}>
                      <td className="mono">{m.fecha}</td>
                      <td className="mono">{m.numero ?? "—"}</td>
                      <td>{m.descripcion}</td>
                      <td>{m.tercero ?? "—"}</td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {m.debito}
                      </td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {m.credito}
                      </td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {m.saldo_acumulado}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <dl className="balance">
                <div>
                  <dt>Saldo final de {cuentaSeleccionada?.nombre}</dt>
                  <dd>{saldoFinal}</dd>
                </div>
              </dl>
            </>
          )}
        </section>
      )}
    </div>
  );
}
