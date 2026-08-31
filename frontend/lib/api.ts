const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export type Empresa = {
  id: string;
  nit: string;
  razon_social: string;
};

export type Tercero = {
  id: string;
  tipo_doc: string;
  num_doc: string;
  nombre: string;
};

export type Cuenta = {
  id: string;
  codigo: string;
  nombre: string;
  naturaleza: "debito" | "credito";
  activa: boolean;
};

export type LineaComprobante = {
  cuenta_id: string;
  tercero_id?: string | null;
  debito: string;
  credito: string;
  descripcion?: string | null;
};

export type Comprobante = {
  id: string;
  empresa_id: string;
  numero: number | null;
  fecha: string;
  descripcion: string;
  estado: "borrador" | "contabilizado" | "reversado" | "reversion";
  comprobante_original_id: string | null;
  lineas: LineaComprobante[];
};

export type MovimientoLibroMayor = {
  fecha: string;
  numero: number | null;
  comprobante_id: string;
  descripcion: string;
  tercero: string | null;
  debito: string;
  credito: string;
  saldo_acumulado: string;
};

export type ExogenaHistorial = {
  id: string;
  anio_gravable: number;
  umbral_uvt: string;
  uvt_valor_usado: string;
  total_registros: number;
  total_valor_bruto: string;
  generado_en: string;
};

/**
 * Cliente HTTP mínimo. Decisión de diseño: se evitó agregar una librería de
 * fetching (SWR/React Query) para mantener el alcance del frontend acotado;
 * en una siguiente iteración se recomienda incorporarla para cacheo,
 * revalidación y manejo de estados de carga más robusto.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Error ${res.status}`);
  }
  return res.json();
}

export const api = {
  listarEmpresas: () => request<Empresa[]>(`/empresas`),

  crearEmpresa: (data: { nit: string; razon_social: string }) =>
    request<Empresa>(`/empresas`, { method: "POST", body: JSON.stringify(data) }),

  listarCuentas: (empresaId: string) => request<Cuenta[]>(`/empresas/${empresaId}/cuentas`),

  crearCuenta: (
    empresaId: string,
    data: { codigo: string; nombre: string; naturaleza: "debito" | "credito" }
  ) =>
    request<Cuenta>(`/empresas/${empresaId}/cuentas`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listarTerceros: (empresaId: string) => request<Tercero[]>(`/empresas/${empresaId}/terceros`),

  crearTercero: (empresaId: string, data: { tipo_doc: string; num_doc: string; nombre: string }) =>
    request<Tercero>(`/empresas/${empresaId}/terceros`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  crearBorrador: (data: {
    empresa_id: string;
    fecha: string;
    descripcion: string;
    lineas: LineaComprobante[];
  }) => request<Comprobante>("/comprobantes", { method: "POST", body: JSON.stringify(data) }),

  contabilizar: (comprobanteId: string) =>
    request<Comprobante>(`/comprobantes/${comprobanteId}/contabilizar`, { method: "POST" }),

  libroMayor: (params: {
    empresa_id: string;
    cuenta_id: string;
    fecha_inicio: string;
    fecha_fin: string;
  }) => {
    const qs = new URLSearchParams(params).toString();
    return request<MovimientoLibroMayor[]>(`/libro-mayor?${qs}`);
  },

  exogenaHistorial: (empresaId: string) =>
    request<ExogenaHistorial[]>(`/exogena/historial?empresa_id=${empresaId}`),

  exogenaGenerarUrl: () => `${API_URL}/exogena/generar`,
  exogenaArchivoUrl: (id: string) => `${API_URL}/exogena/historial/${id}/archivo`,
};
