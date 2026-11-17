"use client";

import React, { useEffect, useState } from "react";
import { airManagerApi } from "@/lib/api";
import type { CredentialProfileItem, RouterItem, SubnetItem } from "@/lib/types";

export default function DiscoveryPage() {
  const [subnets, setSubnets] = useState<SubnetItem[]>([]);
  const [routers, setRouters] = useState<RouterItem[]>([]);
  const [credentials, setCredentials] = useState<CredentialProfileItem[]>([]);
  const [cidrInput, setCidrInput] = useState("");
  const [subnetNameInput, setSubnetNameInput] = useState("");
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

  const handleAddSubnet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cidrInput || !subnetNameInput) return;
    try {
      await airManagerApi.createSubnet({ cidr_block: cidrInput, name: subnetNameInput });
      setCidrInput("");
      setSubnetNameInput("");
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">
          Hybrid Multi-Subnet Discovery &amp; Ubiquiti Router Integration
        </h1>
        <p className="text-sm text-slate-400">
          Configured CIDR scanners, EdgeOS/UISP neighbor enrichment, and encrypted airOS 8 credentials
        </p>
      </div>

      {banner && (
        <div className="px-4 py-3 rounded-xl bg-blue-950/80 border border-blue-700 text-blue-200 text-sm flex justify-between">
          <span>{banner}</span>
          <button onClick={() => setBanner(null)} className="text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Configured Subnets */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <h2 className="text-base font-semibold text-white">1. Configured Routed Subnets (CIDR)</h2>
        <form onSubmit={(e) => void handleAddSubnet(e)} className="flex flex-wrap gap-3">
          <input
            type="text"
            value={cidrInput}
            onChange={(e) => setCidrInput(e.target.value)}
            placeholder="CIDR (e.g. 10.10.30.0/24)"
            className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white"
          />
          <input
            type="text"
            value={subnetNameInput}
            onChange={(e) => setSubnetNameInput(e.target.value)}
            placeholder="Subnet / Site Description"
            className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white flex-1"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
          >
            + Add Routed CIDR
          </button>
        </form>

        <div className="overflow-x-auto">
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

      {/* Ubiquiti Routers */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <h2 className="text-base font-semibold text-white">
          2. Optional Ubiquiti Router Integration (ARP &amp; DHCP Lease Helpers)
        </h2>
        <div className="overflow-x-auto">
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

      {/* Credentials */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
        <h2 className="text-base font-semibold text-white">
          3. Encrypted airOS 8 &amp; Router Credential Profiles (Fernet Vault)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {credentials.map((c) => (
            <div
              key={c.id}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between"
            >
              <div>
                <div className="font-semibold text-sm text-white">{c.name}</div>
                <div className="text-xs text-slate-400">
                  User: <span className="font-mono text-slate-200">{c.username}</span> · HTTPS Port:{" "}
                  {c.https_port}
                </div>
              </div>
              {c.is_default && (
                <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-300 text-xs font-semibold">
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
