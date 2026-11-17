import type {
  AgentTaskItem,
  CredentialProfileItem,
  DashboardSummary,
  DeviceItem,
  RouterItem,
  SubnetItem,
  WirelessClient,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errBody.detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const airManagerApi = {
  getDashboardSummary: () => apiRequest<DashboardSummary>("/api/v1/dashboard/summary"),

  listClients: (params?: { ap_device_id?: string; health_filter?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.ap_device_id) q.set("ap_device_id", params.ap_device_id);
    if (params?.health_filter) q.set("health_filter", params.health_filter);
    if (params?.search) q.set("search", params.search);
    const qs = q.toString();
    return apiRequest<{ items: WirelessClient[]; total: number }>(`/api/v1/clients${qs ? `?${qs}` : ""}`);
  },

  getClientDetail: (clientId: string) => apiRequest<WirelessClient>(`/api/v1/clients/${clientId}`),

  kickClient: (clientId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem; client: WirelessClient }>(
      `/api/v1/clients/${clientId}/kick`,
      { method: "POST" }
    ),

  setClientAcl: (clientId: string, action: "block" | "unblock") =>
    apiRequest<{ message: string; task: AgentTaskItem; client: WirelessClient }>(
      `/api/v1/clients/${clientId}/acl`,
      { method: "POST", body: JSON.stringify({ action }) }
    ),

  rebootClient: (clientId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem; client: WirelessClient }>(
      `/api/v1/clients/${clientId}/reboot`,
      { method: "POST" }
    ),

  probeClient: (clientId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem; client: WirelessClient }>(
      `/api/v1/clients/${clientId}/probe`,
      { method: "POST" }
    ),

  listDevices: (params?: { role?: string; subnet_id?: string; status?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.role) q.set("role", params.role);
    if (params?.subnet_id) q.set("subnet_id", params.subnet_id);
    if (params?.status) q.set("status", params.status);
    if (params?.search) q.set("search", params.search);
    const qs = q.toString();
    return apiRequest<{ items: DeviceItem[]; total: number }>(`/api/v1/devices${qs ? `?${qs}` : ""}`);
  },

  getDeviceDetail: (deviceId: string) => apiRequest<DeviceItem>(`/api/v1/devices/${deviceId}`),

  rebootDevice: (deviceId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem }>(`/api/v1/devices/${deviceId}/reboot`, {
      method: "POST",
    }),

  probeDevice: (deviceId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem }>(`/api/v1/devices/${deviceId}/probe`, {
      method: "POST",
    }),

  listSubnets: () => apiRequest<{ items: SubnetItem[]; total: number }>("/api/v1/subnets"),

  createSubnet: (payload: {
    cidr_block: string;
    name: string;
    site_name?: string;
    vlan_id?: number;
    scan_interval_sec?: number;
  }) =>
    apiRequest<SubnetItem>("/api/v1/subnets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  scanSubnet: (subnetId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem }>(`/api/v1/subnets/${subnetId}/scan`, {
      method: "POST",
    }),

  deleteSubnet: (subnetId: string) =>
    apiRequest<{ deleted: boolean }>(`/api/v1/subnets/${subnetId}`, { method: "DELETE" }),

  listRouters: () => apiRequest<{ items: RouterItem[]; total: number }>("/api/v1/routers"),

  createRouter: (payload: { name: string; host_ip: string; router_type: string; port?: number }) =>
    apiRequest<RouterItem>("/api/v1/routers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  syncRouter: (routerId: string) =>
    apiRequest<{ message: string; task: AgentTaskItem }>(`/api/v1/routers/${routerId}/sync`, {
      method: "POST",
    }),

  listCredentials: () =>
    apiRequest<{ items: CredentialProfileItem[]; total: number }>("/api/v1/credentials"),

  createCredential: (payload: {
    name: string;
    username: string;
    password: string;
    https_port?: number;
    is_default?: boolean;
  }) =>
    apiRequest<CredentialProfileItem>("/api/v1/credentials", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listTasks: () => apiRequest<{ items: AgentTaskItem[]; total: number }>("/api/v1/tasks"),

  probeLiveIp: (payload: {
    ip_address: string;
    username: string;
    password?: string;
    port?: number;
    save_credential?: boolean;
  }) =>
    apiRequest<{ message: string; device: DeviceItem; task: AgentTaskItem }>(
      "/api/v1/discovery/probe-ip",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  clearDemoDevices: () =>
    apiRequest<{ message: string }>("/api/v1/discovery/clear-devices", { method: "POST" }),

  simulateIpDrift: () =>
    apiRequest<{ message: string }>("/api/v1/discovery/simulate-ip-drift", { method: "POST" }),
};

export function formatUptime(seconds: number): string {
  if (!seconds || seconds <= 0) return "0m";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function formatThroughput(kbps: number): string {
  if (!kbps || kbps <= 0) return "0 kbps";
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(1)} Mbps`;
  return `${Math.round(kbps)} kbps`;
}
