import type { Metadata } from "next";
import { Fraunces, Outfit } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Outfit({ subsets: ["latin"], variable: "--font-sans" });
const serif = Fraunces({ subsets: ["latin"], variable: "--font-serif" });

export const metadata: Metadata = {
  title: "Soccer Bet Scout",
  description: "Europe club Elo and per-match score breakdowns. Men's competitions only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body>
        <div className="shell">
          <header className="topbar">
            <Link href="/" className="brand">
              <strong>Scout</strong>
              <span>Europe</span>
            </Link>
            <nav className="nav">
              <Link href="/">Rankings</Link>
              <Link href="/matches">Slate</Link>
              <Link href="/backtest">Backtest</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
