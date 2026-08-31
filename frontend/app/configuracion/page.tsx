"use client";

import { useEffect, useState } from "react";
import { api, Cuenta, Empresa, Tercero } from "@/lib/api";
import { useEmpresaSeleccionada } from "@/components/SelectorEmpresa";

export default function ConfiguracionPage() {
  const { empresaId, setEmpresaId } = useEmpresaSeleccionada();
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [terceros, setTerceros] = useState<Tercero[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const [nit, setNit] = useState("");
  const [razonSocial, setRazonSocial] = useState("");

  const [codigoCuenta, setCodigoCuenta] = useState("");
  const [nombreCuenta, setNombreCuenta] = useState("");
  const [naturalezaCuenta, setNaturalezaCuenta] = useState<"debito" | "credito">("debito");

  const [tipoDocTercero, setTipoDocTercero] = useState("CC");
  const [numDocTercero, setNumDocTercero] = useState("");
  const [nombreTercero, setNombreTercero] = useState("");

  useEffect(() => {
    cargarEmpresas();
  }, []);

  useEffect(() => {
    if (!empresaId) return;
    cargarDetalle(empresaId);
  }, [empresaId]);

  function cargarEmpresas() {
    api.listarEmpresas().then(setEmpresas).catch((e) => setError(e.message));
  }

  function cargarDetalle(id: string) {
    api.listarCuentas(id).then(setCuentas).catch((e) => setError(e.message));
    api.listarTerceros(id).then(setTerceros).catch((e) => setError(e.message));
  }

  function avisar(texto: string) {
    setAviso(texto);
    setTimeout(() => setAviso(null), 3000);
  }

  async function crearEmpresa() {
    setError(null);
    try {
      const empresa = await api.crearEmpresa({ nit, razon_social: razonSocial });
      setNit("");
      setRazonSocial("");
      cargarEmpresas();
      setEmpresaId(empresa.id);
      avisar(`Empresa "${empresa.razon_social}" creada`);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function crearCuenta() {
    if (!empresaId) return;
    setError(null);
    try {
      await api.crearCuenta(empresaId, {
        codigo: codigoCuenta,
        nombre: nombreCuenta,
        naturaleza: naturalezaCuenta,
      });
      setCodigoCuenta("");
      setNombreCuenta("");
      cargarDetalle(empresaId);
      avisar("Cuenta creada");
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function crearTercero() {
    if (!empresaId) return;
    setError(null);
    try {
      await api.crearTercero(empresaId, {
        tipo_doc: tipoDocTercero,
        num_doc: numDocTercero,
        nombre: nombreTercero,
      });
      setNumDocTercero("");
      setNombreTercero("");
      cargarDetalle(empresaId);
      avisar("Tercero creado");
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="stack-lg">
      <header className="page-header">
        <h1>Configuración</h1>
        <p className="page-lead">
          Da de alta la empresa, su plan de cuentas y los terceros con los que vas a contabilizar.
          Esto solo se hace una vez por empresa.
        </p>
      </header>

      {error && <div className="banner banner--error">{error}</div>}
      {aviso && <div className="banner banner--ok">{aviso}</div>}

      <section className="panel">
        <h2>1. Empresa</h2>
        <div className="form-row">
          <div className="field">
            <label>NIT (con dígito de verificación)</label>
            <input placeholder="900123456-8" value={nit} onChange={(e) => setNit(e.target.value)} />
          </div>
          <div className="field field--grow">
            <label>Razón social</label>
            <input value={razonSocial} onChange={(e) => setRazonSocial(e.target.value)} />
          </div>
          <button className="btn btn--primary" onClick={crearEmpresa} disabled={!nit || !razonSocial}>
            Crear empresa
          </button>
        </div>

        {empresas.length > 0 && (
          <div className="field field--inline" style={{ marginTop: "1.25rem" }}>
            <label>Empresa activa</label>
            <select value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
              <option value="">Seleccionar...</option>
              {empresas.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.razon_social} · {emp.nit}
                </option>
              ))}
            </select>
          </div>
        )}
      </section>

      {empresaId && (
        <>
          <section className="panel">
            <h2>2. Plan de cuentas</h2>
            <div className="form-row">
              <div className="field">
                <label>Código</label>
                <input
                  placeholder="1105"
                  value={codigoCuenta}
                  onChange={(e) => setCodigoCuenta(e.target.value)}
                  className="mono"
                />
              </div>
              <div className="field field--grow">
                <label>Nombre</label>
                <input
                  placeholder="Caja"
                  value={nombreCuenta}
                  onChange={(e) => setNombreCuenta(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Naturaleza</label>
                <select
                  value={naturalezaCuenta}
                  onChange={(e) => setNaturalezaCuenta(e.target.value as "debito" | "credito")}
                >
                  <option value="debito">Débito</option>
                  <option value="credito">Crédito</option>
                </select>
              </div>
              <button
                className="btn btn--primary"
                onClick={crearCuenta}
                disabled={!codigoCuenta || !nombreCuenta}
              >
                Agregar cuenta
              </button>
            </div>

            {cuentas.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Nombre</th>
                    <th>Naturaleza</th>
                  </tr>
                </thead>
                <tbody>
                  {cuentas.map((c) => (
                    <tr key={c.id}>
                      <td className="mono">{c.codigo}</td>
                      <td>{c.nombre}</td>
                      <td>
                        <span className={`badge badge--${c.naturaleza}`}>{c.naturaleza}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty-hint">Aún no hay cuentas. Agrega al menos dos para poder contabilizar.</p>
            )}
          </section>

          <section className="panel">
            <h2>3. Terceros</h2>
            <div className="form-row">
              <div className="field">
                <label>Tipo doc.</label>
                <select value={tipoDocTercero} onChange={(e) => setTipoDocTercero(e.target.value)}>
                  <option value="CC">CC</option>
                  <option value="NIT">NIT</option>
                  <option value="CE">CE</option>
                </select>
              </div>
              <div className="field">
                <label>Número</label>
                <input
                  value={numDocTercero}
                  onChange={(e) => setNumDocTercero(e.target.value)}
                  className="mono"
                />
              </div>
              <div className="field field--grow">
                <label>Nombre</label>
                <input value={nombreTercero} onChange={(e) => setNombreTercero(e.target.value)} />
              </div>
              <button
                className="btn btn--primary"
                onClick={crearTercero}
                disabled={!numDocTercero || !nombreTercero}
              >
                Agregar tercero
              </button>
            </div>

            {terceros.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Documento</th>
                    <th>Nombre</th>
                  </tr>
                </thead>
                <tbody>
                  {terceros.map((t) => (
                    <tr key={t.id}>
                      <td className="mono">
                        {t.tipo_doc} {t.num_doc}
                      </td>
                      <td>{t.nombre}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty-hint">Aún no hay terceros registrados (son opcionales por línea contable).</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
