"use client";

import React from "react";
import type { WirelessClient } from "@/lib/types";
import { formatThroughput, formatUptime } from "@/lib/api";

interface Props {
  client: WirelessClient | null;
  onClose: () => void;
  onAction: (clientId: string, action: "kick" | "block" | "unblock" | "reboot" | "probe") => void;
}

export function ClientDetailDrawer({ client, onClose, onAction }: Props) {
  if (!client) return null;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex justify-end">
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full overflow-y-auto p-6 text-slate-100 shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-800 pb-4">
          <div>
            <span className="text-xs uppercase tracking-wider text-blue-400 font-semibold">
              {client.remote_model} · {client.remote_firmware}
            </span>
            <h2 className="text-xl font-bold text-white mt-0.5">{client.remote_hostname}</h2>
            <p className="text-xs text-slate-400 font-mono mt-1">
              MAC: {client.client_mac} · IP: {client.last_known_ip || "N/A"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300"
          >
            Close
          </button>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 my-5">
          <button
            onClick={() => onAction(client.id, "kick")}
            className="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
          >
            Kick / Reconnect
          </button>
          <button
            onClick={() => onAction(client.id, "probe")}
            className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200"
          >
            Live RF Probe
          </button>
          <button
            onClick={() => onAction(client.id, "reboot")}
            className="px-3 py-2 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-xs font-semibold text-white"
          >
            Reboot CPE
          </button>
          <button
            onClick={() => onAction(client.id, client.is_blocked ? "unblock" : "block")}
            className={`px-3 py-2 rounded-lg text-xs font-semibold text-white ${
              client.is_blocked
                ? "bg-emerald-600 hover:bg-emerald-500"
                : "bg-rose-600 hover:bg-rose-500"
            }`}
          >
            {client.is_blocked ? "Unblock MAC" : "Block MAC (ACL)"}
          </button>
        </div>

        {/* RF Link Telemetry */}
        <div className="space-y-4">
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Dual-Chain airMAX AC Link Telemetry
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-xs text-slate-400">Local RX Signal (at AP)</div>
                <div className="text-lg font-bold text-white">{client.signal_dbm} dBm</div>
                <div className="text-xs text-slate-400 mt-0.5">
                  Chain 0: {client.chain0_dbm} dBm / Chain 1: {client.chain1_dbm} dBm
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Chain Imbalance</div>
                <div
                  className={`text-lg font-bold ${
                    client.chain_imbalance_db >= 5 ? "text-amber-400" : "text-emerald-400"
                  }`}
                >
                  Δ {client.chain_imbalance_db} dB
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  Noise Floor: {client.noise_floor_dbm} dBm (SNR {client.snr_db} dB)
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400">airMAX Capacity / Quality</div>
                <div className="text-base font-semibold text-white">
                  {client.airmax_capacity_pct}% / {client.airmax_quality_pct}%
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400">PHY Modulation Rate</div>
                <div className="text-base font-semibold text-white">
                  TX {client.tx_rate_mbps} / RX {client.rx_rate_mbps} Mbps
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Live Throughput</div>
                <div className="text-base font-semibold text-blue-400">
                  ↓ {formatThroughput(client.tx_throughput_kbps)} / ↑{" "}
                  {formatThroughput(client.rx_throughput_kbps)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-400">Distance &amp; Session Uptime</div>
                <div className="text-base font-semibold text-white">
                  {(client.distance_meters / 1000).toFixed(2)} km ·{" "}
                  {formatUptime(client.connection_uptime_sec)}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Parent LiteAP GPS Sector
            </h3>
            <div className="text-sm font-medium text-white">{client.ap_hostname}</div>
            <div className="text-xs text-slate-400 font-mono mt-0.5">
              IP: {client.ap_ip} · MAC: {client.ap_mac} · SSID: {client.ap_ssid} (
              {client.ap_frequency_mhz} MHz / {client.ap_channel_width_mhz} MHz)
            </div>
          </div>

          {client.ip_history && client.ip_history.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Routed IP Address History (MAC Canonical Identity)
              </h3>
              <div className="space-y-2">
                {client.ip_history.map((h) => (
                  <div
                    key={h.id}
                    className="flex items-center justify-between text-xs border-b border-slate-900 pb-1.5"
                  >
                    <span className="font-mono text-slate-200">{h.ip_address}</span>
                    <span className="text-slate-400">{h.discovery_source}</span>
                    <span className="text-slate-500">
                      {new Date(h.last_seen_at).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
