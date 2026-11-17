export interface WirelessClient {
  id: string;
  ap_device_id: string;
  client_device_id: string | null;
  client_mac: string;
  last_known_ip: string | null;
  remote_hostname: string;
  remote_model: string;
  remote_firmware: string;
  is_connected: boolean;
  is_blocked: boolean;
  signal_dbm: number;
  remote_signal_dbm: number;
  chain0_dbm: number;
  chain1_dbm: number;
  chain_imbalance_db: number;
  noise_floor_dbm: number;
  snr_db: number;
  tx_rate_mbps: number;
  rx_rate_mbps: number;
  airmax_capacity_pct: number;
  airmax_quality_pct: number;
  distance_meters: number;
  connection_uptime_sec: number;
  tx_bytes: number;
  rx_bytes: number;
  tx_throughput_kbps: number;
  rx_throughput_kbps: number;
  tx_latency_ms: number;
  last_seen_at: string;
  ap_hostname: string;
  ap_ip: string;
  ap_mac: string;
  ap_ssid: string | null;
  ap_frequency_mhz: number | null;
  ap_channel_width_mhz: number | null;
  subnet_name?: string | null;
  subnet_cidr?: string | null;
  link_health: "good" | "warning" | "critical" | "blocked" | "offline";
  ip_history?: DeviceIpHistoryItem[];
  recent_tasks?: AgentTaskItem[];
}

export interface DeviceIpHistoryItem {
  id: number;
  device_id: string;
  ip_address: string;
  subnet_cidr: string | null;
  discovery_source: string;
  first_seen_at: string;
  last_seen_at: string;
  hostname?: string;
  mac_address?: string;
  model?: string;
  role?: string;
}

export interface DeviceItem {
  id: string;
  mac_address: string;
  current_ip: string;
  hostname: string;
  model: string;
  product_code: string | null;
  role: "ap" | "station" | "unknown";
  ssid: string | null;
  firmware_version: string | null;
  frequency_mhz: number | null;
  channel_width_mhz: number | null;
  tx_power_dbm: number | null;
  noise_floor_dbm: number | null;
  cpu_load_pct: number;
  memory_used_pct: number;
  uptime_sec: number;
  gps_lat: number | null;
  gps_lon: number | null;
  status: "online" | "degraded" | "unreachable" | "auth_failed";
  subnet_id: string | null;
  subnet_name?: string | null;
  subnet_cidr?: string | null;
  connected_clients_count: number;
  total_tx_kbps: number;
  total_rx_kbps: number;
  last_seen_at: string;
  ip_history?: DeviceIpHistoryItem[];
  clients?: WirelessClient[];
}

export interface SubnetItem {
  id: string;
  cidr_block: string;
  name: string;
  site_name: string | null;
  vlan_id: number | null;
  scan_enabled: boolean;
  scan_interval_sec: number;
  default_credential_id: string | null;
  credential_name?: string | null;
  device_count: number;
  last_scanned_at: string | null;
  last_discovered_count: number;
}

export interface RouterItem {
  id: string;
  name: string;
  host_ip: string;
  router_type: "edgerouter" | "unifi" | "uisp";
  port: number;
  credential_id: string | null;
  credential_name?: string | null;
  enabled: boolean;
  last_synced_at: string | null;
  last_sync_status: string;
  neighbors_found: number;
}

export interface CredentialProfileItem {
  id: string;
  name: string;
  username: string;
  https_port: number;
  is_default: boolean;
  created_at: string;
}

export interface AgentTaskItem {
  id: string;
  task_type: string;
  target_device_id: string | null;
  target_client_id: string | null;
  device_hostname?: string | null;
  client_hostname?: string | null;
  client_mac?: string | null;
  payload: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed";
  result?: Record<string, unknown> | null;
  error_message?: string | null;
  requested_by: string;
  created_at: string;
  completed_at?: string | null;
}

export interface DashboardSummary {
  kpis: {
    total_devices: number;
    online_devices: number;
    total_aps: number;
    managed_stations: number;
    total_clients: number;
    connected_clients: number;
    weak_signal_count: number;
    chain_imbalance_count: number;
    low_capacity_count: number;
    blocked_clients_count: number;
    routed_subnets_count: number;
    routers_count: number;
    aggregate_tx_mbps: number;
    aggregate_rx_mbps: number;
  };
  sectors: DeviceItem[];
  attention_clients: WirelessClient[];
  recent_ip_history: DeviceIpHistoryItem[];
  recent_tasks: AgentTaskItem[];
}
