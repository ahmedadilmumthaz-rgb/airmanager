"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { airManagerApi, formatThroughput } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const loadSummary = async () => {
    const data = await airManagerApi.getDashboardSummary();
    setSummary(data);
  };

  useEffect(() => {
    void loadSummary();
  }, []);

  const triggerIpDriftSimulation = async () => {
    const res = await airManagerApi.simulateIpDrift();
    setBanner(res.message);
    await loadSummary();
  };

  if (!summary) {
    return <div className="text-slate-400 py-10 text-sm">Loading network telemetry...</div>;
  }

  const { kpis } = summary;

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">
            Ubiquiti airOS 8 Network Overview
          </h1>
          <p className="text-xs sm:text-sm text-slate-400">
            Multi-subnet LiteAP GPS sectors &amp; connected Loco 5AC station telemetry
          </p>
        </div>
        <div className="grid grid-cols-2 sm:flex items-center gap-2">
          <button
            onClick={() => void triggerIpDriftSimulation()}
            className="px-3 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 text-center"
          >
            Simulate IP Drift
          </button>
          <Link
            href="/clients"
            className="px-3.5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white text-center"
          >
            Manage Clients →
          </Link>
        </div>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-xs sm:text-sm flex items-center justify-between gap-2">
          <span>{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4">
          <div className="text-[11px] sm:text-xs text-slate-400 uppercase">Connected Clients</div>
          <div className="text-xl sm:text-2xl font-bold text-white mt-1">
            {kpis.connected_clients} / {kpis.total_clients}
          </div>
          <div className="text-[11px] sm:text-xs text-blue-400 mt-1">
            ↓ {kpis.aggregate_tx_mbps}M · ↑ {kpis.aggregate_rx_mbps}M
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4">
          <div className="text-[11px] sm:text-xs text-slate-400 uppercase">LiteAP GPS Sectors</div>
          <div className="text-xl sm:text-2xl font-bold text-white mt-1">
            {kpis.total_aps} Active
          </div>
          <div className="text-[11px] sm:text-xs text-emerald-400 mt-1">
            {kpis.routed_subnets_count} Routed Subnets
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4">
          <div className="text-[11px] sm:text-xs text-slate-400 uppercase">RF Link Warnings</div>
          <div className="text-lg sm:text-2xl font-bold text-amber-400 mt-1">
            {kpis.weak_signal_count} Weak · {kpis.chain_imbalance_count} ΔCh
          </div>
          <div className="text-[11px] sm:text-xs text-slate-400 mt-1">
            {kpis.low_capacity_count} low airMAX cap
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4">
          <div className="text-[11px] sm:text-xs text-slate-400 uppercase">Router Helpers</div>
          <div className="text-xl sm:text-2xl font-bold text-white mt-1">
            {kpis.routers_count} Gateways
          </div>
          <div className="text-[11px] sm:text-xs text-slate-400 mt-1">EdgeOS / UISP ARP sync</div>
        </div>
      </div>

      {/* Sectors Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5">
        <h2 className="text-sm sm:text-base font-semibold text-white mb-3">
          LiteAP GPS Access Point Sectors
        </h2>

        {/* Mobile Sector Cards */}
        <div className="md:hidden space-y-2.5">
          {summary.sectors.map((sec) => (
            <div
              key={sec.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-white truncate">{sec.hostname}</span>
                <span className="text-xs font-semibold text-emerald-400 shrink-0">
                  {sec.connected_clients_count} stations
                </span>
              </div>
              <div className="text-xs font-mono text-slate-400 break-all">
                {sec.current_ip} · {sec.mac_address}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-300 pt-1">
                <span>
                  {sec.ssid} ({sec.frequency_mhz} MHz / {sec.channel_width_mhz} MHz)
                </span>
                <span className="text-blue-400 font-medium">
                  ↓ {formatThroughput(sec.total_tx_kbps)} / ↑ {formatThroughput(sec.total_rx_kbps)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop Sector Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <th className="py-2.5">Sector Hostname</th>
                <th className="py-2.5">Management IP &amp; MAC</th>
                <th className="py-2.5">SSID &amp; Channel</th>
                <th className="py-2.5">Noise Floor</th>
                <th className="py-2.5">Connected Clients</th>
                <th className="py-2.5">Aggregate Throughput</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {summary.sectors.map((sec) => (
                <tr key={sec.id}>
                  <td className="py-3 font-semibold text-white">{sec.hostname}</td>
                  <td className="py-3 font-mono text-xs text-slate-300">
                    {sec.current_ip} · {sec.mac_address}
                  </td>
                  <td className="py-3 text-slate-300">
                    {sec.ssid} ({sec.frequency_mhz} MHz / {sec.channel_width_mhz} MHz)
                  </td>
                  <td className="py-3 text-slate-300">{sec.noise_floor_dbm} dBm</td>
                  <td className="py-3 font-semibold text-emerald-400">
                    {sec.connected_clients_count} stations
                  </td>
                  <td className="py-3 text-blue-400">
                    ↓ {formatThroughput(sec.total_tx_kbps)} / ↑{" "}
                    {formatThroughput(sec.total_rx_kbps)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent MAC-Based IP History */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5">
        <h2 className="text-sm sm:text-base font-semibold text-white mb-3">
          Canonical MAC Identity &amp; Routed IP History Log
        </h2>

        {/* Mobile IP History List */}
        <div className="md:hidden space-y-2">
          {summary.recent_ip_history.map((h) => (
            <div
              key={h.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs space-y-1"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-white truncate">{h.hostname}</span>
                <span className="font-mono text-blue-400 font-semibold">{h.ip_address}</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-mono">{h.mac_address}</span>
                <span>{h.discovery_source}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop IP History Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <th className="py-2">Radio Hostname</th>
                <th className="py-2">Canonical MAC</th>
                <th className="py-2">Observed IP Address</th>
                <th className="py-2">Discovery Source</th>
                <th className="py-2">Last Verified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {summary.recent_ip_history.map((h) => (
                <tr key={h.id}>
                  <td className="py-2.5 font-medium text-white">{h.hostname}</td>
                  <td className="py-2.5 font-mono text-xs text-slate-300">{h.mac_address}</td>
                  <td className="py-2.5 font-mono text-xs text-blue-400">{h.ip_address}</td>
                  <td className="py-2.5 text-xs text-slate-300">{h.discovery_source}</td>
                  <td className="py-2.5 text-xs text-slate-400">
                    {new Date(h.last_seen_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
