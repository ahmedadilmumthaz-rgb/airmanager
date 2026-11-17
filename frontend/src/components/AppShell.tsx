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
  { href: "/clients", label: "Connected Clients", shortLabel: "Clients", badge: "Primary" },
  { href: "/", label: "Overview Dashboard", shortLabel: "Overview" },
  { href: "/devices", label: "Sectors & Radios", shortLabel: "Radios" },
  { href: "/discovery", label: "Routed Subnets & Routers", shortLabel: "Discovery" },
  { href: "/tasks", label: "Agent Audit Log", shortLabel: "Audit" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [authReady, setAuthReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<string>("admin");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Login form state
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

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
    setMobileMenuOpen(false);
  };

  if (!authReady) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center text-sm px-4">
        Verifying AirManager session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-lg text-white shrink-0">
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
              className="w-full py-3 rounded-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-sm font-semibold text-white transition"
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row">
      {/* Mobile Sticky Top Header */}
      <header className="md:hidden sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-xs text-white">
            U
          </div>
          <div>
            <div className="font-semibold text-sm text-white leading-tight">AirManager</div>
            <div className="text-[11px] text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              airOS 8 · {currentUser}
            </div>
          </div>
        </div>

        <button
          onClick={() => setMobileMenuOpen((prev) => !prev)}
          aria-label="Toggle Menu"
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
        >
          {mobileMenuOpen ? "✕ Close" : "☰ Menu"}
        </button>
      </header>

      {/* Mobile Slide-Down Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 top-[53px] z-50 bg-black/75 backdrop-blur-xs">
          <div className="bg-slate-900 border-b border-slate-800 p-4 space-y-3 shadow-2xl">
            <nav className="space-y-1.5">
              {NAV_ITEMS.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium ${
                      active
                        ? "bg-blue-600 text-white"
                        : "text-slate-200 bg-slate-950/60 hover:bg-slate-800"
                    }`}
                  >
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 font-semibold">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
              <span className="text-slate-400">
                Signed in as <strong className="text-white">{currentUser}</strong>
              </span>
              <button
                onClick={handleSignOut}
                className="px-3 py-1.5 rounded-lg bg-rose-900/80 text-rose-100 font-medium"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 bg-slate-900 border-r border-slate-800 flex-col justify-between shrink-0">
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

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 overflow-y-auto p-3.5 pb-24 sm:p-6 md:pb-8 lg:p-8">
        {children}
      </main>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-slate-900/95 backdrop-blur border-t border-slate-800 grid grid-cols-5">
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`py-2.5 px-1 flex flex-col items-center justify-center text-[11px] font-medium transition ${
                active ? "text-blue-400 bg-slate-800/60" : "text-slate-400"
              }`}
            >
              <span className="truncate">{item.shortLabel}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
