"use client";

import React, { useEffect, useState } from "react";
import { airManagerApi } from "@/lib/api";
import type { CredentialProfileItem, RouterItem, SubnetItem } from "@/lib/types";

export default function DiscoveryPage() {
  const [subnets, setSubnets] = useState<SubnetItem[]>([]);
  const [routers, setRouters] = useState<RouterItem[]>([]);
  const [credentials, setCredentials] = useState<CredentialProfileItem[]>([]);

  // Live Radio Web Login & Probe State (defaults to 'admin' and HTTP port 80)
  const [probeIp, setProbeIp] = useState("10.61.200.185");
  const [radioUser, setRadioUser] = useState("admin");
  const [radioPassword, setRadioPassword] = useState("");
  const [radioPort, setRadioPort] = useState<number>(80);
  const [probing, setProbing] = useState(false);

  // Add Subnet State
  const [cidrInput, setCidrInput] = useState("10.61.200.0/24");
  const [subnetNameInput, setSubnetNameInput] = useState("Production airOS 8 Subnet");
  const [banner, setBanner] = useState<string | null>(null);

  const loadAll = async () => {
    const [s, r, c] = await Promise.all([
      airManagerApi.listSubnets(),
      airManagerApi.listRouters(),
      airManagerApi.listCredentials(),
    ]);
    setSubnets(s.items);
    setRouters(r.items);
    setCredentials(c.items);
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const handleProbeLiveRadio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!probeIp) return;
    setProbing(true);
    try {
      const res = await airManagerApi.probeLiveIp({
        ip_address: probeIp,
        username: radioUser || "admin",
        password: radioPassword,
        port: radioPort || 80,
        save_credential: true,
      });
      setBanner(res.message);
      await loadAll();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Live radio probe failed");
    } finally {
      setProbing(false);
    }
  };

  const handleSaveCredentialOnly = async () => {
    if (!radioPassword) {
      setBanner("Enter the radio web login password first");
      return;
    }
    try {
      await airManagerApi.createCredential({
        name: "WISP-Standard-airOS8",
        username: radioUser || "admin",
        password: radioPassword,
        https_port: radioPort || 80,
        is_default: true,
      });
      setBanner(`Saved default airOS 8 web login (${radioUser || "admin"} on port ${radioPort})`);
      await loadAll();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to save credential");
    }
  };

  const handleAddSubnet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cidrInput || !subnetNameInput) return;
    try {
      await airManagerApi.createSubnet({ cidr_block: cidrInput, name: subnetNameInput });
      setBanner(`Added routed subnet ${cidrInput}`);
      await loadAll();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to add subnet");
    }
  };

  const handleScanSubnet = async (id: string) => {
    const res = await airManagerApi.scanSubnet(id);
    setBanner(res.message);
    await loadAll();
  };

  const handleSyncRouter = async (id: string) => {
    const res = await airManagerApi.syncRouter(id);
    setBanner(res.message);
    await loadAll();
  };

  const handleClearDemo = async () => {
    const res = await airManagerApi.clearDemoDevices();
    setBanner(res.message);
    await loadAll();
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">
            airOS 8 Web Dashboard Login &amp; Multi-Subnet Discovery
          </h1>
          <p className="text-xs sm:text-sm text-slate-400">
            Authenticate as <code className="text-blue-400">admin</code> via HTTP (:80) / HTTPS (:443) to import LiteAP GPS sectors &amp; Loco 5AC clients
          </p>
        </div>
        <button
          onClick={() => void handleClearDemo()}
          className="w-full sm:w-auto px-3.5 py-2.5 rounded-lg bg-rose-900/70 hover:bg-rose-800 text-xs font-semibold text-rose-100"
        >
          Clear Demo Radios
        </button>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-blue-950/80 border border-blue-700 text-blue-200 text-xs sm:text-sm flex justify-between gap-2">
          <span className="break-words">{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Live airOS 8 Web Login & Direct Radio Probe */}
      <div className="bg-slate-900 border border-blue-800/60 rounded-xl p-4 sm:p-5 space-y-4">
        <div>
          <h2 className="text-sm sm:text-base font-semibold text-white">
            1. airOS 8 Web Login &amp; Live Radio Probe (HTTP Port 80 / HTTPS 443)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Logs into <code className="text-slate-300">POST /api/auth</code> on the radio web dashboard, saves your default <code className="text-slate-300">admin</code> credentials encrypted in the vault, and pulls <code className="text-slate-300">/status.cgi</code> &amp; <code className="text-slate-300">/sta.cgi</code>.
          </p>
        </div>

        <form onSubmit={(e) => void handleProbeLiveRadio(e)} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Radio IP Address</label>
            <input
              type="text"
              value={probeIp}
              onChange={(e) => setProbeIp(e.target.value)}
              placeholder="10.61.200.185"
              className="w-full px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Web Login Username</label>
            <input
              type="text"
              value={radioUser}
              onChange={(e) => setRadioUser(e.target.value)}
              placeholder="admin"
              className="w-full px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Web Login Password</label>
            <input
              type="password"
              value={radioPassword}
              onChange={(e) => setRadioPassword(e.target.value)}
              placeholder="Enter admin password..."
              className="w-full px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Web Port (80 or 443)</label>
            <input
              type="number"
              value={radioPort}
              onChange={(e) => setRadioPort(Number(e.target.value))}
              className="w-full px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white font-mono"
            />
          </div>
          <div className="sm:col-span-2 lg:col-span-1 flex items-end gap-2">
            <button
              type="submit"
              disabled={probing}
              className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
            >
              {probing ? "Logging in..." : "Login & Probe"}
            </button>
            <button
              type="button"
              onClick={() => void handleSaveCredentialOnly()}
              className="px-3 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 whitespace-nowrap"
            >
              Save Login
            </button>
          </div>
        </form>
      </div>

      {/* 2. Configured Subnets */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-4">
        <h2 className="text-sm sm:text-base font-semibold text-white">
          2. Configured Routed Subnets (CIDR)
        </h2>
        <form onSubmit={(e) => void handleAddSubnet(e)} className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
          <input
            type="text"
            value={cidrInput}
            onChange={(e) => setCidrInput(e.target.value)}
            placeholder="CIDR (e.g. 10.61.200.0/24)"
            className="px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white font-mono"
          />
          <input
            type="text"
            value={subnetNameInput}
            onChange={(e) => setSubnetNameInput(e.target.value)}
            placeholder="Subnet / Site Description"
            className="px-3 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white"
          />
          <button
            type="submit"
            className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
          >
            + Add Routed CIDR
          </button>
        </form>

        {/* Mobile Subnet Cards */}
        <div className="md:hidden space-y-2.5">
          {subnets.map((s) => (
            <div
              key={s.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-bold text-sm text-blue-400">{s.cidr_block}</span>
                <span className="text-xs font-semibold text-emerald-400">
                  {s.device_count} radios
                </span>
              </div>
              <div className="text-xs text-slate-200">
                {s.name} {s.vlan_id ? `· VLAN ${s.vlan_id}` : ""}
              </div>
              <div className="flex items-center justify-between gap-2 pt-1">
                <span className="text-[11px] text-slate-500">
                  {s.last_scanned_at
                    ? `Scanned ${new Date(s.last_scanned_at).toLocaleTimeString()}`
                    : "Never scanned"}
                </span>
                <button
                  onClick={() => void handleScanSubnet(s.id)}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
                >
                  Scan Subnet Now
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop Subnet Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <th className="py-2">CIDR Block</th>
                <th className="py-2">Name / Site</th>
                <th className="py-2">VLAN</th>
                <th className="py-2">Discovered Radios</th>
                <th className="py-2">Last Scanned</th>
                <th className="py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {subnets.map((s) => (
                <tr key={s.id}>
                  <td className="py-3 font-mono font-semibold text-blue-400">{s.cidr_block}</td>
                  <td className="py-3 text-white">{s.name}</td>
                  <td className="py-3 text-slate-400">{s.vlan_id || "—"}</td>
                  <td className="py-3 text-emerald-400 font-semibold">{s.device_count} radios</td>
                  <td className="py-3 text-xs text-slate-400">
                    {s.last_scanned_at ? new Date(s.last_scanned_at).toLocaleString() : "Never"}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => void handleScanSubnet(s.id)}
                      className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-xs font-medium text-white"
                    >
                      Scan Subnet Now
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Ubiquiti Routers */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-4">
        <h2 className="text-sm sm:text-base font-semibold text-white">
          3. Optional Ubiquiti Router Integration (ARP &amp; DHCP Lease Helpers)
        </h2>

        {/* Mobile Router Cards */}
        <div className="md:hidden space-y-2.5">
          {routers.map((r) => (
            <div
              key={r.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-white">{r.name}</span>
                <span className="font-mono text-xs text-blue-400">{r.host_ip}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="uppercase">{r.router_type}</span>
                <span className="text-emerald-400 font-medium">{r.neighbors_found} MACs</span>
              </div>
              <div className="flex items-center justify-between gap-2 pt-1">
                <span className="text-[11px] text-slate-500 truncate">{r.last_sync_status}</span>
                <button
                  onClick={() => void handleSyncRouter(r.id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 shrink-0"
                >
                  Sync ARP / DHCP
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop Router Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <th className="py-2">Router Name</th>
                <th className="py-2">Host IP</th>
                <th className="py-2">Platform</th>
                <th className="py-2">Neighbors Harvested</th>
                <th className="py-2">Sync Status</th>
                <th className="py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {routers.map((r) => (
                <tr key={r.id}>
                  <td className="py-3 font-semibold text-white">{r.name}</td>
                  <td className="py-3 font-mono text-xs text-blue-400">{r.host_ip}</td>
                  <td className="py-3 uppercase text-xs text-slate-300">{r.router_type}</td>
                  <td className="py-3 text-emerald-400 font-medium">{r.neighbors_found} MACs</td>
                  <td className="py-3 text-xs text-slate-400">{r.last_sync_status}</td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => void handleSyncRouter(r.id)}
                      className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200"
                    >
                      Sync ARP / DHCP
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Credentials */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
        <h2 className="text-sm sm:text-base font-semibold text-white">
          4. Encrypted airOS 8 &amp; Router Credential Profiles (Fernet Vault)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {credentials.map((c) => (
            <div
              key={c.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between gap-2"
            >
              <div className="min-w-0">
                <div className="font-semibold text-sm text-white truncate">{c.name}</div>
                <div className="text-xs text-slate-400">
                  User: <span className="font-mono text-slate-200">{c.username}</span> · Web Port:{" "}
                  {c.https_port}
                </div>
              </div>
              {c.is_default && (
                <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-300 text-xs font-semibold shrink-0">
                  Default Profile
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
