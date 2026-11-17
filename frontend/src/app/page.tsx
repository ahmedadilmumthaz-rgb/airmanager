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
    return <div className="text-slate-400 py-10">Loading network telemetry...</div>;
  }

  const { kpis } = summary;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Ubiquiti airOS 8 Network Overview</h1>
          <p className="text-sm text-slate-400">
            Multi-subnet LiteAP GPS sectors &amp; connected Loco 5AC station telemetry
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void triggerIpDriftSimulation()}
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200"
          >
            Simulate Radio IP Change
          </button>
          <Link
            href="/clients"
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
          >
            Manage Connected Clients →
          </Link>
        </div>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-sm flex items-center justify-between">
          <span>{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 uppercase">Connected Loco 5AC Clients</div>
          <div className="text-2xl font-bold text-white mt-1">
            {kpis.connected_clients} / {kpis.total_clients}
          </div>
          <div className="text-xs text-blue-400 mt-1">
            ↓ {kpis.aggregate_tx_mbps} Mbps · ↑ {kpis.aggregate_rx_mbps} Mbps
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 uppercase">LiteAP GPS Sectors</div>
          <div className="text-2xl font-bold text-white mt-1">{kpis.total_aps} Active</div>
          <div className="text-xs text-emerald-400 mt-1">
            Across {kpis.routed_subnets_count} Routed Subnets
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 uppercase">RF Link Warnings</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            {kpis.weak_signal_count} Weak · {kpis.chain_imbalance_count} Imbalanced
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {kpis.low_capacity_count} links below 65% airMAX cap
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 uppercase">Ubiquiti Router Helpers</div>
          <div className="text-2xl font-bold text-white mt-1">{kpis.routers_count} Gateways</div>
          <div className="text-xs text-slate-400 mt-1">EdgeOS / UISP ARP &amp; DHCP sync</div>
        </div>
      </div>

      {/* Sectors Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-3">
          LiteAP GPS Access Point Sectors
        </h2>
        <div className="overflow-x-auto">
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
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-3">
          Canonical MAC Identity &amp; Routed IP History Log
        </h2>
        <div className="overflow-x-auto">
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
