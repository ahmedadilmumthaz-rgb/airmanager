"use client";

import React, { useEffect, useState } from "react";
import { airManagerApi } from "@/lib/api";
import type { AgentTaskItem } from "@/lib/types";

export default function TasksPage() {
  const [tasks, setTasks] = useState<AgentTaskItem[]>([]);

  const loadTasks = async () => {
    const res = await airManagerApi.listTasks();
    setTasks(res.items);
  };

  useEffect(() => {
    void loadTasks();
  }, []);

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">
            Linux Agent Task Queue &amp; Audit Log
          </h1>
          <p className="text-xs sm:text-sm text-slate-400">
            Execution history of station kicks, MAC ACL updates, CPE reboots, and subnet scans
          </p>
        </div>
        <button
          onClick={() => void loadTasks()}
          className="w-full sm:w-auto px-3.5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200"
        >
          Refresh Log
        </button>
      </div>

      {/* Mobile Task Cards */}
      <div className="md:hidden space-y-2.5">
        {tasks.map((t) => (
          <div
            key={t.id}
            className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-2"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs font-bold text-blue-400">{t.task_type}</span>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                  t.status === "completed"
                    ? "bg-emerald-950 text-emerald-300"
                    : t.status === "failed"
                    ? "bg-rose-950 text-rose-300"
                    : "bg-amber-950 text-amber-300"
                }`}
              >
                {t.status}
              </span>
            </div>
            <div className="text-xs text-white font-medium">
              {t.client_hostname || t.device_hostname || "Multi-Subnet"}
              {t.client_mac ? (
                <span className="font-mono text-slate-400 ml-1">({t.client_mac})</span>
              ) : null}
            </div>
            <div className="text-[11px] font-mono text-slate-400 bg-slate-950 rounded p-2 break-all">
              {JSON.stringify(t.result || t.payload)}
            </div>
            <div className="text-[11px] text-slate-500">
              {new Date(t.created_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Task Table */}
      <div className="hidden md:block bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs uppercase text-slate-400 bg-slate-950/50">
              <th className="py-3 px-4">Task Type</th>
              <th className="py-3 px-3">Target Sector / Client</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3">Payload / Diagnostic Result</th>
              <th className="py-3 px-4">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {tasks.map((t) => (
              <tr key={t.id}>
                <td className="py-3 px-4 font-mono text-xs font-semibold text-blue-400">
                  {t.task_type}
                </td>
                <td className="py-3 px-3 text-slate-200">
                  <div>{t.client_hostname || t.device_hostname || "Multi-Subnet"}</div>
                  {t.client_mac && (
                    <div className="text-xs font-mono text-slate-400">{t.client_mac}</div>
                  )}
                </td>
                <td className="py-3 px-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      t.status === "completed"
                        ? "bg-emerald-950 text-emerald-300"
                        : t.status === "failed"
                        ? "bg-rose-950 text-rose-300"
                        : "bg-amber-950 text-amber-300"
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="py-3 px-3 font-mono text-xs text-slate-400 max-w-md truncate">
                  {JSON.stringify(t.result || t.payload)}
                </td>
                <td className="py-3 px-4 text-xs text-slate-400">
                  {new Date(t.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
