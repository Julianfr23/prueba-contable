import type { Metadata } from "next";
import { IBM_Plex_Mono, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mayor — aplicación contable",
  description: "Motor contable: comprobantes, libro mayor e información exógena",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${serif.variable} ${mono.variable}`}>
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            <span className="brand-mark">M</span>
            <span className="brand-name">Mayor</span>
          </Link>
          <nav className="topnav">
            <Link href="/configuracion">Configuración</Link>
            <Link href="/comprobantes">Comprobantes</Link>
            <Link href="/libro-mayor">Libro mayor</Link>
            <Link href="/exogena">Exógena</Link>
          </nav>
        </header>
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
