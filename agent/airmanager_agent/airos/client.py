from __future__ import annotations

"""
Ubiquiti airOS 8 HTTPS Management Client & Protocol Parser.
Supports LiteAP GPS (AP mode) and NanoStation Loco 5AC (Station mode) running airOS 8.x:
- Session authentication via POST /api/auth (AIROS_SESSIONID + X-CSRF-ID)
- Device status via GET /status.cgi
- Associated station list via GET /sta.cgi
- Station kick / reconnect via POST /kick.cgi
- Wireless MAC ACL block/unblock via /cfg.cgi & /apply.cgi
- Device reboot via POST /reboot.cgi
"""

from http.cookiejar import CookieJar
import json
import re
import ssl
import time
from typing import Any
from urllib import parse, request


def normalize_mac(mac: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    if len(cleaned) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return ":".join(cleaned[i : i + 2].upper() for i in range(0, 12, 2))


def classify_airos_model(raw_model: str, product_code: str = "") -> tuple[str, str]:
    """Normalizes Ubiquiti airOS 8 device strings to ('LiteAP GPS' | 'Loco 5AC' | ..., code)."""
    combined = f"{raw_model} {product_code}".lower()
    if "liteap" in combined or "lap-gps" in combined:
        return "LiteAP GPS", "LAP-GPS"
    if "loco" in combined or "ns-5acl" in combined or "loco5ac" in combined:
        return "Loco 5AC", "NS-5ACL"
    return raw_model or "Ubiquiti airMAX AC", product_code or "AIRMAX-AC"


def parse_airos_status_json(ip_address: str, status_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Parses airOS 8 `/status.cgi` JSON response into a canonical AirManager device dictionary.
    """
    host = status_payload.get("host", {})
    wireless = status_payload.get("wireless", {})
    gps = status_payload.get("gps", {})
    interfaces = status_payload.get("interfaces", [])

    # Determine canonical hardware MAC address (prefer ath0/wlan0 orwireless.apmac, fallback eth0)
    mac_candidate = wireless.get("apmac") or host.get("hwaddr")
    for iface in interfaces:
        if iface.get("ifname") in ("ath0", "wlan0", "br0") and iface.get("hwaddr"):
            mac_candidate = iface["hwaddr"]
            break
    if not mac_candidate and interfaces:
        mac_candidate = interfaces[0].get("hwaddr")
    mac_address = normalize_mac(str(mac_candidate or "78:8A:20:00:00:01"))

    raw_model = str(host.get("devmodel") or "LiteAP GPS")
    prod_code = str(host.get("PrdID") or "")
    model, code = classify_airos_model(raw_model, prod_code)

    wmode = str(wireless.get("mode") or "ap-ptmp").lower()
    role = "ap" if wmode.startswith("ap") else ("station" if wmode.startswith("sta") else "unknown")

    freq_raw = wireless.get("frequency") or 5745
    if isinstance(freq_raw, str):
        freq_match = re.search(r"(\d{4})", freq_raw)
        frequency_mhz = int(freq_match.group(1)) if freq_match else 5745
    else:
        frequency_mhz = int(freq_raw)

    total_ram = float(host.get("totalram") or 65536)
    free_ram = float(host.get("freeram") or 32768)
    mem_used_pct = round(max(0.0, min(100.0, ((total_ram - free_ram) / max(1.0, total_ram)) * 100.0)), 1)

    return {
        "mac_address": mac_address,
        "current_ip": ip_address,
        "hostname": str(host.get("hostname") or f"{model}-{mac_address[-5:].replace(':', '')}"),
        "model": model,
        "product_code": code,
        "role": role,
        "ssid": wireless.get("essid"),
        "firmware_version": str(host.get("fwversion") or "WA.v8.7.11"),
        "frequency_mhz": frequency_mhz,
        "channel_width_mhz": int(wireless.get("chanbw") or 40),
        "tx_power_dbm": int(wireless.get("txpower") or 20),
        "noise_floor_dbm": int(wireless.get("noisef") or -94),
        "cpu_load_pct": round(float(host.get("cpuload") or 0.0), 1),
        "memory_used_pct": mem_used_pct,
        "uptime_sec": int(host.get("uptime") or 0),
        "gps_lat": float(gps["lat"]) if gps.get("lat") is not None else None,
        "gps_lon": float(gps["lon"]) if gps.get("lon") is not None else None,
        "status": "online",
    }


def parse_airos_sta_json(
    sta_list: list[dict[str, Any]],
    previous_counters: dict[str, tuple[float, int, int]] | None = None,
) -> list[dict[str, Any]]:
    """
    Parses airOS 8 `/sta.cgi` JSON array of connected stations (`Loco 5AC` CPEs)
    into AirManager `wireless_clients` records, calculating live throughput from byte deltas.
    """
    now_ts = time.time()
    parsed_clients: list[dict[str, Any]] = []

    for sta in sta_list:
        c_mac = normalize_mac(str(sta.get("mac") or "78:8A:20:00:00:02"))
        remote = sta.get("remote", {}) or {}
        airmax = sta.get("airmax", {}) or {}
        chain_rssi = sta.get("chain_rssi") or []
        noise = int(sta.get("noisefloor") or -94)
        sig = int(sta.get("signal") or -62)

        # airOS 8 reports chain_rssi as RSSI above noise floor or direct dBm per chain
        if len(chain_rssi) >= 2:
            r0, r1 = int(chain_rssi[0]), int(chain_rssi[1])
            chain0 = r0 if r0 < 0 else (noise + r0)
            chain1 = r1 if r1 < 0 else (noise + r1)
        else:
            chain0 = sig
            chain1 = sig

        tx_bytes = int(sta.get("tx_bytes") or (sta.get("stats", {}) or {}).get("tx_bytes") or 0)
        rx_bytes = int(sta.get("rx_bytes") or (sta.get("stats", {}) or {}).get("rx_bytes") or 0)

        tx_kbps = float(sta.get("tx_throughput_kbps") or 0.0)
        rx_kbps = float(sta.get("rx_throughput_kbps") or 0.0)

        if previous_counters is not None and c_mac in previous_counters:
            prev_ts, prev_tx, prev_rx = previous_counters[c_mac]
            dt = max(0.5, now_ts - prev_ts)
            if tx_bytes >= prev_tx:
                tx_kbps = round(((tx_bytes - prev_tx) * 8.0) / (dt * 1000.0), 1)
            if rx_bytes >= prev_rx:
                rx_kbps = round(((rx_bytes - prev_rx) * 8.0) / (dt * 1000.0), 1)

        if previous_counters is not None:
            previous_counters[c_mac] = (now_ts, tx_bytes, rx_bytes)

        dl_cap = int(airmax.get("downlink_capacity") or airmax.get("capacity") or 85)
        ul_cap = int(airmax.get("uplink_capacity") or dl_cap)
        avg_cap = int(round((dl_cap + ul_cap) / 2.0))
        qual = int(airmax.get("quality") or min(99, max(40, avg_cap + 5)))

        model_name, _ = classify_airos_model(str(remote.get("platform") or "Loco 5AC"))

        parsed_clients.append(
            {
                "client_mac": c_mac,
                "last_known_ip": sta.get("lastip") or remote.get("ipaddr"),
                "remote_hostname": str(remote.get("hostname") or f"Loco5AC-{c_mac[-5:].replace(':', '')}"),
                "remote_model": model_name,
                "remote_firmware": str(remote.get("version") or "WA.v8.7.11"),
                "is_connected": True,
                "signal_dbm": sig,
                "remote_signal_dbm": int(remote.get("signal") or (sig - 1)),
                "chain0_dbm": chain0,
                "chain1_dbm": chain1,
                "noise_floor_dbm": noise,
                "tx_rate_mbps": float(sta.get("tx") or 300.0),
                "rx_rate_mbps": float(sta.get("rx") or 300.0),
                "airmax_capacity_pct": avg_cap,
                "airmax_quality_pct": qual,
                "distance_meters": int(sta.get("distance") or remote.get("distance") or 600),
                "connection_uptime_sec": int(sta.get("uptime") or 0),
                "tx_bytes": tx_bytes,
                "rx_bytes": rx_bytes,
                "tx_throughput_kbps": tx_kbps,
                "rx_throughput_kbps": rx_kbps,
                "tx_latency_ms": float(sta.get("tx_latency") or 2.0),
            }
        )

    return parsed_clients


def update_system_cfg_mac_acl(system_cfg_text: str, client_mac: str, block: bool) -> str:
    """
    Updates an airOS 8 `/tmp/system.cfg` configuration string to block or unblock a station MAC
    using the `wireless.1.mac_acl` directives.
    """
    target_mac = normalize_mac(client_mac)
    lines = [line.strip() for line in system_cfg_text.splitlines() if line.strip()]
    filtered: list[str] = []
    existing_denied: list[str] = []

    acl_mac_re = re.compile(r"^wireless\.1\.mac_acl\.\d+\.mac=([0-9A-Fa-f:]+)$")
    for line in lines:
        if line.startswith("wireless.1.mac_acl."):
            m = acl_mac_re.match(line)
            if m:
                mac_val = normalize_mac(m.group(1))
                if mac_val != target_mac and mac_val not in existing_denied:
                    existing_denied.append(mac_val)
            continue
        filtered.append(line)

    if block and target_mac not in existing_denied:
        existing_denied.append(target_mac)

    filtered.append("wireless.1.mac_acl.status=enabled" if existing_denied else "wireless.1.mac_acl.status=disabled")
    filtered.append("wireless.1.mac_acl.policy=deny")
    for idx, m_addr in enumerate(existing_denied, start=1):
        filtered.append(f"wireless.1.mac_acl.{idx}.mac={m_addr}")
        filtered.append(f"wireless.1.mac_acl.{idx}.status=enabled")

    return "\n".join(filtered) + "\n"


class AirOS8Client:
    """
    HTTPS Session Client for Ubiquiti airOS 8 radios (`LiteAP GPS` & `Loco 5AC`).
    Uses self-signed TLS context scoped strictly to the target radio IP.
    """

    def __init__(
        self,
        host_ip: str,
        username: str = "ubnt",
        password: str = "ubnt",
        https_port: int = 443,
        timeout_sec: float = 5.0,
    ) -> None:
        self.host_ip = host_ip
        self.username = username
        self.password = password
        self.https_port = https_port
        self.timeout_sec = timeout_sec
        self.base_url = f"https://{host_ip}:{https_port}"
        self.csrf_token: str | None = None
        self.cookie_jar = CookieJar()

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = request.build_opener(
            request.HTTPSHandler(context=ssl_ctx),
            request.HTTPCookieProcessor(self.cookie_jar),
        )

    def _request_json(
        self,
        method: str,
        path: str,
        form_data: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "AirManager-Linux-Agent/1.0",
        }
        if self.csrf_token:
            headers["X-CSRF-ID"] = self.csrf_token

        data_bytes: bytes | None = None
        if json_data is not None:
            data_bytes = json.dumps(json_data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_data is not None:
            data_bytes = parse.urlencode(form_data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = request.Request(url, data=data_bytes, headers=headers, method=method)
        with self._opener.open(req, timeout=self.timeout_sec) as resp:
            csrf_hdr = resp.headers.get("X-CSRF-ID")
            if csrf_hdr:
                self.csrf_token = csrf_hdr
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    def login(self) -> bool:
        """Authenticates against airOS 8 `/api/auth`."""
        resp = self._request_json(
            "POST",
            "/api/auth",
            form_data={"username": self.username, "password": self.password},
        )
        return bool(resp is not None)

    def fetch_status(self) -> dict[str, Any]:
        raw = self._request_json("GET", "/status.cgi")
        return parse_airos_status_json(self.host_ip, raw)

    def fetch_stations(
        self, previous_counters: dict[str, tuple[float, int, int]] | None = None
    ) -> list[dict[str, Any]]:
        raw = self._request_json("GET", "/sta.cgi")
        sta_list = raw if isinstance(raw, list) else raw.get("stations", [])
        return parse_airos_sta_json(sta_list, previous_counters=previous_counters)

    def kick_station(self, client_mac: str) -> dict[str, Any]:
        mac = normalize_mac(client_mac)
        return self._request_json("POST", "/kick.cgi", form_data={"sta_mac": mac, "ifname": "ath0"})

    def fetch_system_cfg(self) -> str:
        """Downloads current `/tmp/system.cfg` from airOS 8 via GET `/cfg.cgi`."""
        url = f"{self.base_url}/cfg.cgi"
        headers = {"User-Agent": "AirManager-Linux-Agent/1.0"}
        if self.csrf_token:
            headers["X-CSRF-ID"] = self.csrf_token
        req = request.Request(url, headers=headers, method="GET")
        with self._opener.open(req, timeout=self.timeout_sec) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def upload_and_apply_system_cfg(self, cfg_content: str) -> dict[str, Any]:
        """Uploads modified `system.cfg` via multipart/form-data to `/cfg.cgi` and triggers `/apply.cgi`."""
        boundary = f"----AirManagerBoundary{int(time.time() * 1000)}"
        body_lines = [
            f"--{boundary}",
            'Content-Disposition: form-data; name="cfgfile"; filename="system.cfg"',
            "Content-Type: application/octet-stream",
            "",
            cfg_content,
            f"--{boundary}--",
            "",
        ]
        body_bytes = "\r\n".join(body_lines).encode("utf-8")
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AirManager-Linux-Agent/1.0",
        }
        if self.csrf_token:
            headers["X-CSRF-ID"] = self.csrf_token

        upload_req = request.Request(
            f"{self.base_url}/cfg.cgi",
            data=body_bytes,
            headers=headers,
            method="POST",
        )
        with self._opener.open(upload_req, timeout=self.timeout_sec) as resp:
            _ = resp.read()

        apply_res = self._request_json("POST", "/apply.cgi", form_data={"testmode": ""})
        return {"applied": True, "response": apply_res}

    def set_mac_acl(self, client_mac: str, block: bool) -> dict[str, Any]:
        """Reads `/cfg.cgi`, updates `wireless.1.mac_acl.*` for `client_mac`, and applies it."""
        current_cfg = self.fetch_system_cfg()
        updated_cfg = update_system_cfg_mac_acl(current_cfg, client_mac, block=block)
        apply_result = self.upload_and_apply_system_cfg(updated_cfg)
        return {
            "client_mac": normalize_mac(client_mac),
            "blocked": block,
            **apply_result,
        }

    def reboot(self) -> dict[str, Any]:
        return self._request_json("POST", "/reboot.cgi")
