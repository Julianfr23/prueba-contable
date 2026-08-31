"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Empresa } from "@/lib/api";

export function useEmpresaSeleccionada() {
  const [empresaId, setEmpresaId] = useState("");

  useEffect(() => {
    const guardado = localStorage.getItem("empresa_id");
    if (guardado) setEmpresaId(guardado);
  }, []);

  function seleccionar(id: string) {
    setEmpresaId(id);
    if (id) localStorage.setItem("empresa_id", id);
    else localStorage.removeItem("empresa_id");
  }

  return { empresaId, setEmpresaId: seleccionar };
}

export function SelectorEmpresa({
  empresaId,
  onChange,
}: {
  empresaId: string;
  onChange: (id: string) => void;
}) {
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api
      .listarEmpresas()
      .then(setEmpresas)
      .finally(() => setCargando(false));
  }, []);

  if (!cargando && empresas.length === 0) {
    return (
      <div className="panel panel--empty">
        <p>
          Todavía no hay ninguna empresa registrada. Antes de continuar, crea una en{" "}
          <Link href="/configuracion">Configuración</Link>.
        </p>
      </div>
    );
  }

  return (
    <div className="field field--inline">
      <label htmlFor="selector-empresa">Empresa</label>
      <select id="selector-empresa" value={empresaId} onChange={(e) => onChange(e.target.value)}>
        <option value="">{cargando ? "Cargando..." : "Seleccionar empresa..."}</option>
        {empresas.map((e) => (
          <option key={e.id} value={e.id}>
            {e.razon_social} · {e.nit}
          </option>
        ))}
      </select>
      <Link href="/configuracion" className="link-muted">
        + Nueva empresa
      </Link>
    </div>
  );
}
