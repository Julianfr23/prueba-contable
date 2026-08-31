"use client";

import { useEffect, useState } from "react";
import { api, ExogenaHistorial } from "@/lib/api";
import { SelectorEmpresa, useEmpresaSeleccionada } from "@/components/SelectorEmpresa";

export default function ExogenaPage() {
  const { empresaId, setEmpresaId } = useEmpresaSeleccionada();
  const [anioGravable, setAnioGravable] = useState(new Date().getFullYear() - 1);
  const [umbralUvt, setUmbralUvt] = useState("0");
  const [historial, setHistorial] = useState<ExogenaHistorial[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);

  useEffect(() => {
    if (!empresaId) return;
    cargarHistorial(empresaId);
  }, [empresaId]);

  async function cargarHistorial(id: string) {
    try {
      const data = await api.exogenaHistorial(id);
      setHistorial(data);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function generar() {
    setError(null);
    setGenerando(true);
    try {
      const res = await fetch(api.exogenaGenerarUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          empresa_id: empresaId,
          anio_gravable: anioGravable,
          umbral_uvt: umbralUvt,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? "Error generando el archivo");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `exogena_${anioGravable}.xml`;
      a.click();
      window.URL.revokeObjectURL(url);
      await cargarHistorial(empresaId);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerando(false);
    }
  }

  function redescargar(id: string) {
    window.open(api.exogenaArchivoUrl(id), "_blank");
  }

  return (
    <div className="stack-lg">
      <header className="page-header">
        <h1>Información exógena</h1>
        <p className="page-lead">
          Genera el reporte anual en XML agrupado por tercero, aplicando un umbral mínimo en UVT.
        </p>
      </header>

      <SelectorEmpresa empresaId={empresaId} onChange={setEmpresaId} />

      {empresaId && (
        <>
          <section className="panel">
            <div className="form-row" style={{ marginBottom: 0 }}>
              <div className="field">
                <label>Año gravable</label>
                <input
                  type="number"
                  className="mono"
                  value={anioGravable}
                  onChange={(e) => setAnioGravable(parseInt(e.target.value, 10))}
                />
              </div>
              <div className="field">
                <label>Umbral (UVT)</label>
                <input
                  type="number"
                  step="0.01"
                  className="mono"
                  value={umbralUvt}
                  onChange={(e) => setUmbralUvt(e.target.value)}
                />
              </div>
              <button className="btn btn--primary" onClick={generar} disabled={generando}>
                {generando ? "Generando..." : "Generar y descargar"}
              </button>
            </div>
            {error && (
              <div className="banner banner--error" style={{ marginTop: "1rem" }}>
                {error}
              </div>
            )}
          </section>

          <section className="panel">
            <h2>Historial de generaciones</h2>
            {historial.length === 0 ? (
              <p className="empty-hint">Sin generaciones previas para esta empresa.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Generado</th>
                    <th>Año</th>
                    <th style={{ textAlign: "right" }}>Umbral UVT</th>
                    <th style={{ textAlign: "right" }}>Valor UVT</th>
                    <th style={{ textAlign: "right" }}>Registros</th>
                    <th style={{ textAlign: "right" }}>Total bruto</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((h) => (
                    <tr key={h.id}>
                      <td className="mono">{new Date(h.generado_en).toLocaleString()}</td>
                      <td className="mono">{h.anio_gravable}</td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {h.umbral_uvt}
                      </td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {h.uvt_valor_usado}
                      </td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {h.total_registros}
                      </td>
                      <td className="mono" style={{ textAlign: "right" }}>
                        {h.total_valor_bruto}
                      </td>
                      <td>
                        <button className="btn btn--secondary" onClick={() => redescargar(h.id)}>
                          Descargar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
