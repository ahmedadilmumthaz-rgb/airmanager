"use client";

import React, { useCallback, useEffect, useState } from "react";
import { airManagerApi, formatUptime } from "@/lib/api";
import type { DeviceItem } from "@/lib/types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [selectedDevice, setSelectedDevice] = useState<DeviceItem | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const loadDevices = useCallback(async () => {
    const res = await airManagerApi.listDevices({ role: roleFilter, search });
    setDevices(res.items);
  }, [roleFilter, search]);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  const inspectDevice = async (id: string) => {
    const detail = await airManagerApi.getDeviceDetail(id);
    setSelectedDevice(detail);
  };

  const handleAction = async (id: string, action: "probe" | "reboot") => {
    const res =
      action === "probe"
        ? await airManagerApi.probeDevice(id)
        : await airManagerApi.rebootDevice(id);
    setBanner(res.message);
    await loadDevices();
    if (selectedDevice && selectedDevice.id === id) {
      await inspectDevice(id);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-white">
          Sectors &amp; Managed Radios Inventory
        </h1>
        <p className="text-xs sm:text-sm text-slate-400">
          Permanent MAC-based registry of LiteAP GPS sectors and directly managed Loco 5AC stations
        </p>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-blue-950/80 border border-blue-700 text-blue-200 text-xs sm:text-sm flex justify-between gap-2">
          <span>{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-3 bg-slate-900 border border-slate-800 rounded-xl p-3.5 sm:p-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search hostname, MAC address, or IP..."
          className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white flex-1"
        />
        <div className="grid grid-cols-3 sm:flex gap-2">
          {(["all", "ap", "station"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`px-3 py-2 rounded-lg text-xs font-semibold ${
                roleFilter === r
                  ? "bg-blue-600 text-white"
                  : "bg-slate-950 text-slate-300 border border-slate-800"
              }`}
            >
              {r === "all" ? "All" : r === "ap" ? "LiteAP (AP)" : "Loco 5AC"}
            </button>
          ))}
        </div>
      </div>

      {selectedDevice && (
        <div className="bg-slate-900 border border-blue-700 rounded-xl p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm sm:text-lg font-bold text-white truncate">
              {selectedDevice.hostname} — IP History ({selectedDevice.mac_address})
            </h2>
            <button
              onClick={() => setSelectedDevice(null)}
              className="text-xs px-3 py-1.5 rounded bg-slate-800 text-slate-200 shrink-0"
            >
              ✕ Close
            </button>
          </div>
          <div className="space-y-2">
            {(selectedDevice.ip_history || []).map((h) => (
              <div
                key={h.id}
                className="flex flex-wrap items-center justify-between gap-2 text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2"
              >
                <span className="font-mono text-blue-400 font-semibold">{h.ip_address}</span>
                <span className="text-slate-300">Subnet: {h.subnet_cidr || "Routed"}</span>
                <span className="text-slate-400">Source: {h.discovery_source}</span>
                <span className="text-slate-500">
                  {new Date(h.last_seen_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mobile Radio Cards (< lg) */}
      <div className="lg:hidden space-y-3">
        {devices.map((d) => (
          <div
            key={d.id}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <button
                  onClick={() => void inspectDevice(d.id)}
                  className="font-bold text-base text-white hover:text-blue-400 text-left truncate block"
                >
                  {d.hostname}
                </button>
                <div className="text-xs text-slate-400">
                  {d.model} ·{" "}
                  <span className="text-blue-400 font-semibold">{d.role.toUpperCase()}</span>
                </div>
              </div>
              <span className="font-mono text-xs text-blue-400 bg-slate-950 px-2.5 py-1 rounded border border-slate-800 shrink-0">
                {d.current_ip}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/60">
              <div>
                <div className="text-[10px] uppercase text-slate-500">Canonical MAC</div>
                <div className="font-mono text-slate-200 mt-0.5">{d.mac_address}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">SSID &amp; Channel</div>
                <div className="text-slate-200 mt-0.5 truncate">
                  {d.ssid || "—"} ({d.frequency_mhz} MHz)
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">System Load</div>
                <div className="text-slate-300 mt-0.5">
                  CPU {d.cpu_load_pct}% · RAM {d.memory_used_pct}%
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase text-slate-500">Firmware &amp; Uptime</div>
                <div className="text-slate-300 mt-0.5 truncate">
                  {formatUptime(d.uptime_sec)} · {d.firmware_version}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => void inspectDevice(d.id)}
                className="py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200"
              >
                IP History
              </button>
              <button
                onClick={() => void handleAction(d.id, "probe")}
                className="py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
              >
                Poll Now
              </button>
              <button
                onClick={() => void handleAction(d.id, "reboot")}
                className="py-2 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-xs font-semibold text-white"
              >
                Reboot
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Table (lg+) */}
      <div className="hidden lg:block bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs uppercase text-slate-400 bg-slate-950/50">
              <th className="py-3 px-4">Hostname &amp; Model</th>
              <th className="py-3 px-3">Canonical MAC</th>
              <th className="py-3 px-3">Current IP &amp; Subnet</th>
              <th className="py-3 px-3">RF / Firmware</th>
              <th className="py-3 px-3">CPU / RAM / Uptime</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {devices.map((d) => (
              <tr key={d.id} className="hover:bg-slate-800/40">
                <td className="py-3 px-4">
                  <button
                    onClick={() => void inspectDevice(d.id)}
                    className="font-semibold text-white hover:text-blue-400"
                  >
                    {d.hostname}
                  </button>
                  <div className="text-xs text-slate-400">
                    {d.model} ({d.role.toUpperCase()})
                  </div>
                </td>
                <td className="py-3 px-3 font-mono text-xs text-slate-200">{d.mac_address}</td>
                <td className="py-3 px-3">
                  <div className="font-mono text-xs text-blue-400">{d.current_ip}</div>
                  <div className="text-xs text-slate-400">{d.subnet_cidr || "Routed"}</div>
                </td>
                <td className="py-3 px-3 text-xs text-slate-300">
                  <div>
                    {d.ssid} · {d.frequency_mhz} MHz
                  </div>
                  <div className="text-slate-400">{d.firmware_version}</div>
                </td>
                <td className="py-3 px-3 text-xs text-slate-300">
                  <div>
                    CPU {d.cpu_load_pct}% · RAM {d.memory_used_pct}%
                  </div>
                  <div className="text-slate-400">{formatUptime(d.uptime_sec)}</div>
                </td>
                <td className="py-3 px-4 text-right space-x-2">
                  <button
                    onClick={() => void inspectDevice(d.id)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200"
                  >
                    IP History
                  </button>
                  <button
                    onClick={() => void handleAction(d.id, "probe")}
                    className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-xs text-white"
                  >
                    Poll
                  </button>
                  <button
                    onClick={() => void handleAction(d.id, "reboot")}
                    className="px-2.5 py-1 rounded bg-amber-600/80 hover:bg-amber-600 text-xs text-white"
                  >
                    Reboot
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
