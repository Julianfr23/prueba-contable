import Link from "next/link";

const modulos = [
  {
    href: "/configuracion",
    titulo: "Configuración",
    descripcion: "Crea la empresa, su plan de cuentas y los terceros.",
  },
  {
    href: "/comprobantes",
    titulo: "Comprobantes",
    descripcion: "Registra y contabiliza asientos de partida doble.",
  },
  {
    href: "/libro-mayor",
    titulo: "Libro mayor",
    descripcion: "Consulta el movimiento y saldo de cualquier cuenta.",
  },
  {
    href: "/exogena",
    titulo: "Exógena",
    descripcion: "Genera el reporte tributario anual en XML.",
  },
];

export default function HomePage() {
  return (
    <div className="stack-lg">
      <header className="page-header">
        <h1>Mayor</h1>
        <p className="page-lead">
          Motor contable con partida doble, libro mayor y generación de información exógena.
          Empieza por Configuración si es la primera vez que usas esta empresa.
        </p>
      </header>

      <div className="panel" style={{ padding: 0 }}>
        <table className="table">
          <tbody>
            {modulos.map((m) => (
              <tr key={m.href}>
                <td style={{ width: "220px" }}>
                  <Link href={m.href} style={{ fontWeight: 600, textDecoration: "none" }}>
                    {m.titulo}
                  </Link>
                </td>
                <td style={{ color: "var(--ink-soft)" }}>{m.descripcion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
