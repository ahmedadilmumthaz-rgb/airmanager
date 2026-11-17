"use client";

import React, { useCallback, useEffect, useState } from "react";
import { airManagerApi, formatThroughput, formatUptime } from "@/lib/api";
import type { DeviceItem, WirelessClient } from "@/lib/types";
import { ClientDetailDrawer } from "@/components/ClientDetailDrawer";

const HEALTH_FILTERS = [
  { id: "all", label: "All Clients" },
  { id: "weak_signal", label: "Weak Signal (< -72 dBm)" },
  { id: "chain_imbalance", label: "Chain Imbalance (≥ 5 dB)" },
  { id: "low_capacity", label: "Low Capacity (< 65%)" },
  { id: "blocked", label: "Blocked MAC (ACL)" },
];

export default function ConnectedClientsPage() {
  const [clients, setClients] = useState<WirelessClient[]>([]);
  const [sectors, setSectors] = useState<DeviceItem[]>([]);
  const [selectedSector, setSelectedSector] = useState<string>("all");
  const [healthFilter, setHealthFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [drawerClient, setDrawerClient] = useState<WirelessClient | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [cResp, dResp] = await Promise.all([
        airManagerApi.listClients({
          ap_device_id: selectedSector,
          health_filter: healthFilter,
          search,
        }),
        airManagerApi.listDevices({ role: "ap" }),
      ]);
      setClients(cResp.items);
      setSectors(dResp.items);
    } finally {
      setLoading(false);
    }
  }, [selectedSector, healthFilter, search]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleClientAction = async (
    clientId: string,
    action: "kick" | "block" | "unblock" | "reboot" | "probe"
  ) => {
    try {
      let res;
      if (action === "kick") res = await airManagerApi.kickClient(clientId);
      else if (action === "block" || action === "unblock")
        res = await airManagerApi.setClientAcl(clientId, action);
      else if (action === "reboot") res = await airManagerApi.rebootClient(clientId);
      else res = await airManagerApi.probeClient(clientId);

      setBanner(res.message);
      await loadData();
      if (drawerClient && drawerClient.id === clientId) {
        const updated = await airManagerApi.getClientDetail(clientId);
        setDrawerClient(updated);
      }
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Action failed");
    }
  };

  const openDrawer = async (clientId: string) => {
    const detail = await airManagerApi.getClientDetail(clientId);
    setDrawerClient(detail);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">Connected Client Management</h1>
          <p className="text-xs sm:text-sm text-slate-400">
            Live NanoStation Loco 5AC stations associated across routed LiteAP GPS sectors
          </p>
        </div>
        <button
          onClick={() => void loadData()}
          className="w-full sm:w-auto px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
        >
          Refresh Station Table
        </button>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-blue-950/80 border border-blue-700 text-blue-200 text-xs sm:text-sm flex items-center justify-between gap-2">
          <span>{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 sm:gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search CPE hostname, MAC, or IP..."
            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white placeholder-slate-500"
          />
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white"
          >
            <option value="all">All LiteAP GPS Sectors ({sectors.length})</option>
            {sectors.map((sec) => (
              <option key={sec.id} value={sec.id}>
                {sec.hostname} ({sec.current_ip} · {sec.ssid})
              </option>
            ))}
          </select>
          <div className="flex items-center justify-between md:justify-end text-xs text-slate-400 px-1">
            <span>
              Showing <strong className="text-white mx-1">{clients.length}</strong> station links
            </span>
          </div>
        </div>

        <div className="flex overflow-x-auto pb-1 gap-2">
          {HEALTH_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setHealthFilter(f.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap shrink-0 transition ${
                healthFilter === f.id
                  ? "bg-blue-600 text-white"
                  : "bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-700"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile & Tablet Card View (< lg) */}
      <div className="lg:hidden space-y-3">
        {loading ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-sm text-slate-400">
            Loading connected airOS 8 clients...
          </div>
        ) : clients.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-sm text-slate-400">
            No wireless clients match the current filters.
          </div>
        ) : (
          clients.map((c) => (
            <div
              key={c.id}
              className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <button
                    onClick={() => void openDrawer(c.id)}
                    className="font-bold text-base text-white hover:text-blue-400 text-left truncate block"
                  >
                    {c.remote_hostname}
                  </button>
                  <div className="text-xs text-slate-400 font-mono mt-0.5 break-all">
                    {c.client_mac} · {c.last_known_ip || "No IP"}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold ${
                      c.is_blocked
                        ? "bg-rose-950 text-rose-300 border border-rose-700"
                        : c.signal_dbm < -74
                        ? "bg-rose-950 text-rose-300"
                        : c.signal_dbm < -68
                        ? "bg-amber-950 text-amber-300"
                        : "bg-emerald-950 text-emerald-300"
                    }`}
                  >
                    {c.is_blocked ? "ACL BLOCKED" : `${c.signal_dbm} dBm`}
                  </span>
                  {c.chain_imbalance_db >= 5 && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 text-[10px] font-semibold">
                      Δ{c.chain_imbalance_db} dB Imbalance
                    </span>
                  )}
                </div>
              </div>

              <div className="text-xs text-slate-300 bg-slate-950/70 rounded-lg px-3 py-2 flex flex-wrap items-center justify-between gap-2 border border-slate-800/80">
                <span>
                  Sector: <strong className="text-white">{c.ap_hostname}</strong> ({c.ap_ssid})
                </span>
                <span className="text-slate-400">
                  {(c.distance_meters / 1000).toFixed(2)} km ·{" "}
                  {formatUptime(c.connection_uptime_sec)}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs bg-slate-950/40 rounded-lg p-2.5 border border-slate-800/50">
                <div>
                  <div className="text-[10px] uppercase text-slate-500">Chains</div>
                  <div className="font-medium text-slate-200 mt-0.5">
                    {c.chain0_dbm} / {c.chain1_dbm}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-slate-500">airMAX</div>
                  <div className="font-medium text-slate-200 mt-0.5">
                    {c.airmax_capacity_pct}% / {c.airmax_quality_pct}%
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-slate-500">Throughput</div>
                  <div className="font-medium text-blue-400 mt-0.5">
                    ↓{formatThroughput(c.tx_throughput_kbps)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-2 pt-1">
                <button
                  onClick={() => void openDrawer(c.id)}
                  className="py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200"
                >
                  Details
                </button>
                <button
                  onClick={() => void handleClientAction(c.id, "kick")}
                  className="py-2 rounded-lg bg-blue-600/90 hover:bg-blue-500 text-xs font-semibold text-white"
                >
                  Kick
                </button>
                <button
                  onClick={() =>
                    void handleClientAction(c.id, c.is_blocked ? "unblock" : "block")
                  }
                  className={`py-2 rounded-lg text-xs font-semibold text-white ${
                    c.is_blocked
                      ? "bg-emerald-600 hover:bg-emerald-500"
                      : "bg-rose-700 hover:bg-rose-600"
                  }`}
                >
                  {c.is_blocked ? "Unblock" : "Block"}
                </button>
                <button
                  onClick={() => void handleClientAction(c.id, "reboot")}
                  className="py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200"
                >
                  Reboot
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Desktop Table View (lg+) */}
      <div className="hidden lg:block bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs uppercase text-slate-400 bg-slate-950/50">
              <th className="py-3 px-4">Station CPE (Loco 5AC)</th>
              <th className="py-3 px-3">Parent LiteAP GPS</th>
              <th className="py-3 px-3">Signal &amp; Chains</th>
              <th className="py-3 px-3">airMAX Cap / Qual</th>
              <th className="py-3 px-3">Live Throughput</th>
              <th className="py-3 px-3">Dist / Uptime</th>
              <th className="py-3 px-4 text-right">Client Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400">
                  Loading connected airOS 8 clients...
                </td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400">
                  No wireless clients match the current filters.
                </td>
              </tr>
            ) : (
              clients.map((c) => (
                <tr key={c.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-3 px-4">
                    <button
                      onClick={() => void openDrawer(c.id)}
                      className="font-semibold text-white hover:text-blue-400 text-left"
                    >
                      {c.remote_hostname}
                    </button>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      {c.client_mac} · {c.last_known_ip || "No IP"}
                    </div>
                  </td>

                  <td className="py-3 px-3">
                    <div className="text-slate-200 font-medium">{c.ap_hostname}</div>
                    <div className="text-xs text-slate-400 font-mono">
                      {c.ap_ip} · {c.ap_ssid}
                    </div>
                  </td>

                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-bold ${
                          c.is_blocked
                            ? "bg-rose-950 text-rose-300 border border-rose-700"
                            : c.signal_dbm < -74
                            ? "bg-rose-950 text-rose-300"
                            : c.signal_dbm < -68
                            ? "bg-amber-950 text-amber-300"
                            : "bg-emerald-950 text-emerald-300"
                        }`}
                      >
                        {c.is_blocked ? "ACL BLOCKED" : `${c.signal_dbm} dBm`}
                      </span>
                      {c.chain_imbalance_db >= 5 && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 text-[11px] font-semibold">
                          Δ{c.chain_imbalance_db} dB
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Ch0 {c.chain0_dbm} / Ch1 {c.chain1_dbm} dBm
                    </div>
                  </td>

                  <td className="py-3 px-3">
                    <div className="text-slate-200 font-medium">
                      {c.airmax_capacity_pct}% Cap · {c.airmax_quality_pct}% Qual
                    </div>
                    <div className="text-xs text-slate-400">
                      TX {c.tx_rate_mbps} / RX {c.rx_rate_mbps} Mbps
                    </div>
                  </td>

                  <td className="py-3 px-3">
                    <div className="text-blue-400 font-medium">
                      ↓ {formatThroughput(c.tx_throughput_kbps)}
                    </div>
                    <div className="text-xs text-slate-400">
                      ↑ {formatThroughput(c.rx_throughput_kbps)}
                    </div>
                  </td>

                  <td className="py-3 px-3 text-xs text-slate-300">
                    <div>{(c.distance_meters / 1000).toFixed(2)} km</div>
                    <div className="text-slate-400">{formatUptime(c.connection_uptime_sec)}</div>
                  </td>

                  <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                    <button
                      onClick={() => void handleClientAction(c.id, "kick")}
                      className="px-2.5 py-1 rounded bg-blue-600/90 hover:bg-blue-500 text-xs font-medium text-white"
                    >
                      Kick
                    </button>
                    <button
                      onClick={() =>
                        void handleClientAction(c.id, c.is_blocked ? "unblock" : "block")
                      }
                      className={`px-2.5 py-1 rounded text-xs font-medium text-white ${
                        c.is_blocked
                          ? "bg-emerald-600 hover:bg-emerald-500"
                          : "bg-rose-700 hover:bg-rose-600"
                      }`}
                    >
                      {c.is_blocked ? "Unblock" : "Block"}
                    </button>
                    <button
                      onClick={() => void handleClientAction(c.id, "reboot")}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200"
                    >
                      Reboot
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <ClientDetailDrawer
        client={drawerClient}
        onClose={() => setDrawerClient(null)}
        onAction={(id, act) => void handleClientAction(id, act)}
      />
    </div>
  );
}
