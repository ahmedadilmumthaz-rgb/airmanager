"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  airManagerApi,
  clearAuthSession,
  getAuthToken,
  getAuthUser,
} from "@/lib/api";

const NAV_ITEMS = [
  { href: "/clients", label: "Connected Clients", badge: "Primary" },
  { href: "/", label: "Overview Dashboard" },
  { href: "/devices", label: "Sectors & Radios" },
  { href: "/discovery", label: "Routed Subnets & Routers" },
  { href: "/tasks", label: "Agent Audit Log" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [authReady, setAuthReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<string>("admin");

  // Login form state
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    const checkSession = async () => {
      const tok = getAuthToken();
      if (!tok) {
        setIsAuthenticated(false);
        setAuthReady(true);
        return;
      }
      try {
        const me = await airManagerApi.verifySession();
        setCurrentUser(me.username || getAuthUser() || "admin");
        setIsAuthenticated(true);
      } catch {
        setIsAuthenticated(false);
      } finally {
        setAuthReady(true);
      }
    };

    void checkSession();

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
    };
    window.addEventListener("airmanager-unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("airmanager-unauthorized", handleUnauthorized);
    };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setSigningIn(true);
    try {
      const resp = await airManagerApi.login(username.trim(), password);
      setCurrentUser(resp.username);
      setIsAuthenticated(true);
      setPassword("");
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setSigningIn(false);
    }
  };

  const handleSignOut = () => {
    clearAuthSession();
    setIsAuthenticated(false);
  };

  if (!authReady) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center text-sm">
        Verifying AirManager session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-lg text-white">
              U
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">AirManager Operator Console</h1>
              <p className="text-xs text-slate-400">
                Ubiquiti airOS 8 Multi-Subnet Network Manager
              </p>
            </div>
          </div>

          {loginError && (
            <div className="px-3.5 py-2.5 rounded-lg bg-rose-950/90 border border-rose-800 text-rose-200 text-xs">
              {loginError}
            </div>
          )}

          <form onSubmit={(e) => void handleLogin(e)} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Administrator Username
              </label>
              <input
                type="text"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-blue-600"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Administrator Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter dashboard password..."
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-blue-600"
              />
            </div>

            <button
              type="submit"
              disabled={signingIn}
              className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-semibold text-white transition"
            >
              {signingIn ? "Signing in..." : "Sign In to Dashboard"}
            </button>
          </form>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-500 text-center">
            Protected by JWT Session Auth · Configured in{" "}
            <code className="text-slate-400">/etc/airmanager/airmanager.env</code>
          </div>
        </div>
      </div>
    );
  }

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

        <div className="p-4 border-t border-slate-800 text-xs text-slate-400 space-y-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Linux Routed Agent Active
            </div>
            <div>Hardware: LiteAP GPS &amp; Loco 5AC</div>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium truncate">User: {currentUser}</span>
            <button
              onClick={handleSignOut}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-rose-900/80 hover:text-rose-100 text-slate-300 text-xs font-medium transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-y-auto p-6 lg:p-8">{children}</main>
    </div>
  );
}
