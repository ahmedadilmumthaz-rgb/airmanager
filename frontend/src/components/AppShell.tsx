"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/clients", label: "Connected Clients", badge: "Primary" },
  { href: "/", label: "Overview Dashboard" },
  { href: "/devices", label: "Sectors & Radios" },
  { href: "/discovery", label: "Routed Subnets & Routers" },
  { href: "/tasks", label: "Agent Audit Log" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex">
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0">
        <div>
          <div className="p-5 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white">
                U
              </div>
              <div>
                <h1 className="font-semibold text-sm tracking-wide text-white">AirManager</h1>
                <p className="text-xs text-slate-400">airOS 8 · Multi-Subnet</p>
              </div>
            </div>
          </div>

          <nav className="p-3 space-y-1">
            {NAV_ITEMS.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    active
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                        active ? "bg-blue-800 text-blue-100" : "bg-slate-800 text-blue-400"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800 text-xs text-slate-400 space-y-1">
          <div className="flex items-center gap-2 text-emerald-400 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Linux Routed Agent Active
          </div>
          <div>Hardware: LiteAP GPS &amp; Loco 5AC</div>
          <div>Deployment: Ubuntu Systemd</div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-y-auto p-6 lg:p-8">{children}</main>
    </div>
  );
}
