import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hudební radar",
  description: "Relevantní inzeráty z Hudebního bazaru pro Dream of the Sun.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="cs">
      <body className="antialiased">{children}</body>
    </html>
  );
}
