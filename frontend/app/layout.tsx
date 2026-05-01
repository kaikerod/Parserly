import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Parserly Dashboard",
  description: "Análise ATS de currículos com upload, relatório e checkout PIX.",
  icons: {
    icon: "/icon.svg"
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
