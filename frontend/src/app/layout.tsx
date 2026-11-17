import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "AirManager — Ubiquiti airOS 8 Network Manager",
  description:
    "Multi-subnet Ubiquiti airOS 8 Network Manager for LiteAP GPS sectors and Loco 5AC clients",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
