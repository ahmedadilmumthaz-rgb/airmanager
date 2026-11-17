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
import os
import pty
import re
import select
import ssl
import subprocess
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

    wmode = str(wireless.get("mode") or "ap-ptmp").lower()
    role = "ap" if wmode.startswith("ap") else ("station" if wmode.startswith("sta") else "unknown")

    # Determine canonical hardware MAC address:
    # In AP mode, wireless.apmac is the AP's own WLAN MAC.
    # In Station mode (sta-ptmp-ac), wireless.apmac is the remote AP's MAC, while interfaces[ath0/eth0].hwaddr or host.device_id is the station's own MAC.
    iface_mac = None
    for iface in interfaces:
        if iface.get("ifname") in ("ath0", "wlan0", "br0", "eth0") and iface.get("hwaddr"):
            iface_mac = iface["hwaddr"]
            break
    if not iface_mac and interfaces:
        iface_mac = interfaces[0].get("hwaddr")

    if role == "station":
        mac_candidate = host.get("device_id") or host.get("hwaddr") or iface_mac or wireless.get("apmac")
        parent_ap_mac = normalize_mac(str(wireless["apmac"])) if wireless.get("apmac") else None
    else:
        mac_candidate = wireless.get("apmac") or host.get("device_id") or host.get("hwaddr") or iface_mac
        parent_ap_mac = None

    mac_address = normalize_mac(str(mac_candidate or "78:8A:20:00:00:01"))

    raw_model = str(host.get("devmodel") or "LiteAP GPS")
    prod_code = str(host.get("PrdID") or "")
    model, code = classify_airos_model(raw_model, prod_code)

    freq_raw = wireless.get("frequency") or 5745
    if isinstance(freq_raw, str):
        freq_match = re.search(r"(\d{4})", freq_raw)
        frequency_mhz = int(freq_match.group(1)) if freq_match else 5745
    else:
        frequency_mhz = int(freq_raw)

    total_ram = float(host.get("totalram") or 65536)
    free_ram = float(host.get("freeram") or 32768)
    mem_used_pct = round(max(0.0, min(100.0, ((total_ram - free_ram) / max(1.0, total_ram)) * 100.0)), 1)

    result: dict[str, Any] = {
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

    # airOS 8 embeds `wireless.sta` inside `/status.cgi` on both APs and Stations
    embedded_sta = wireless.get("sta")
    if isinstance(embedded_sta, list) and embedded_sta:
        if role == "ap":
            result["clients"] = parse_airos_sta_json(embedded_sta)
        elif role == "station" and parent_ap_mac:
            sta_entry = embedded_sta[0]
            polling = wireless.get("polling", {}) or {}
            noise = int(wireless.get("noisef") or -92)
            sig = int(sta_entry.get("signal") or wireless.get("signal") or -50)
            chain_rssi = sta_entry.get("chain_rssi") or wireless.get("chain_rssi") or []
            if len(chain_rssi) >= 2:
                r0, r1 = int(chain_rssi[0]), int(chain_rssi[1])
                c0 = r0 if r0 < 0 else (noise + r0)
                c1 = r1 if r1 < 0 else (noise + r1)
            else:
                c0, c1 = sig, sig

            dl_cap = int(polling.get("dl_capacity") or (sta_entry.get("airmax", {}) or {}).get("downlink_capacity") or 85)
            ul_cap = int(polling.get("ul_capacity") or (sta_entry.get("airmax", {}) or {}).get("uplink_capacity") or dl_cap)
            if dl_cap > 100:
                max_kbps = 173300.0 if result["channel_width_mhz"] <= 20 else 400000.0
                dl_cap = min(99, max(10, int(round((dl_cap / max_kbps) * 100.0))))
                ul_cap = min(99, max(10, int(round((ul_cap / max_kbps) * 100.0))))

            result["parent_ap_mac"] = parent_ap_mac
            result["station_link"] = {
                "client_mac": mac_address,
                "last_known_ip": ip_address,
                "remote_hostname": result["hostname"],
                "remote_model": model,
                "remote_firmware": result["firmware_version"],
                "is_connected": True,
                "signal_dbm": sig,
                "remote_signal_dbm": int((sta_entry.get("remote", {}) or {}).get("signal") or sig),
                "chain0_dbm": c0,
                "chain1_dbm": c1,
                "noise_floor_dbm": noise,
                "tx_rate_mbps": float(sta_entry.get("tx") or wireless.get("txrate") or 173.3),
                "rx_rate_mbps": float(sta_entry.get("rx") or wireless.get("rxrate") or 173.3),
                "airmax_capacity_pct": int(round((dl_cap + ul_cap) / 2.0)),
                "airmax_quality_pct": int(polling.get("quality") or 90),
                "distance_meters": int(sta_entry.get("distance") or wireless.get("distance") or 150),
                "connection_uptime_sec": int(sta_entry.get("uptime") or result["uptime_sec"]),
                "tx_bytes": int((sta_entry.get("stats", {}) or {}).get("tx_bytes") or 0),
                "rx_bytes": int((sta_entry.get("stats", {}) or {}).get("rx_bytes") or 0),
                "tx_latency_ms": float(sta_entry.get("tx_latency") or 1.0),
            }

    return result


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


def parse_mca_status_output(ip_address: str, mca_text: str) -> dict[str, Any]:
    """
    Parses airOS 8 `mca-status` CLI output (e.g. `WA.ar934x.v8.7.9`) into a canonical AirManager device dict.
    Handles both the comma-separated header line:
        deviceName=NEL1006,deviceId=E0:63:DA:F2:A1:B9,firmwareVersion=WA.ar934x.v8.7.9...,platform=NanoStation 5AC loco,deviceIp=10.42.200.187
    and the newline-separated key=value lines.
    """
    kv: dict[str, str] = {}
    for idx, raw_line in enumerate(mca_text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        # First line in mca-status is comma-delimited key=value pairs
        segments = line.split(",") if (idx == 0 and "," in line and "deviceId=" in line) else [line]
        for seg in segments:
            if "=" in seg:
                k, v = seg.split("=", 1)
                kv[k.strip()] = v.strip()

    # For station mode (`sta-ptmp-ac`), `deviceId` is the station's own MAC and `apMac` is the remote AP's MAC!
    wmode = (kv.get("wlanOpmode") or "ap-ptmp").lower()
    role = "station" if wmode.startswith("sta") else ("ap" if wmode.startswith("ap") else "unknown")

    if role == "station":
        own_mac_raw = kv.get("deviceId") or kv.get("wlanMac") or kv.get("lanMac") or "78:8A:20:00:00:01"
        parent_ap_mac = normalize_mac(kv["apMac"]) if kv.get("apMac") else None
    else:
        own_mac_raw = kv.get("deviceId") or kv.get("apMac") or kv.get("wlanMac") or "78:8A:20:00:00:01"
        parent_ap_mac = None

    mac = normalize_mac(own_mac_raw)
    raw_model = kv.get("platform") or kv.get("deviceName") or "Loco 5AC"
    model, code = classify_airos_model(raw_model)

    freq_val = int(re.sub(r"[^0-9]", "", kv.get("freq") or kv.get("centerFreq") or "5665") or "5665")
    chan_bw = int(re.sub(r"[^0-9]", "", kv.get("chanbw") or "20") or "20")
    mem_total = float(kv.get("memTotal") or 61960)
    mem_free = float(kv.get("memFree") or 14976)
    mem_pct = round(max(0.0, min(100.0, ((mem_total - mem_free) / max(1.0, mem_total)) * 100.0)), 1)
    cpu_pct = round(float(kv.get("cpuUsage") or kv.get("cpuLoad") or 0.0), 1)

    lat = float(kv["latitude"]) if kv.get("latitude") and float(kv["latitude"]) != 0.0 else None
    lon = float(kv["longitude"]) if kv.get("longitude") and float(kv["longitude"]) != 0.0 else None

    # Calculate airMAX capacity percentage from kbps (or direct pct)
    dl_cap_raw = int(float(kv.get("wlanDownlinkCapacity") or 85))
    ul_cap_raw = int(float(kv.get("wlanUplinkCapacity") or dl_cap_raw))
    if dl_cap_raw > 100:
        # Convert airOS 8 capacity in kbps (e.g. 146640 kbps on 20 MHz) to percentage (0-100%)
        max_theoretical_kbps = 173300.0 if chan_bw <= 20 else (400000.0 if chan_bw <= 40 else 866700.0)
        dl_cap_pct = min(99, max(10, int(round((dl_cap_raw / max_theoretical_kbps) * 100.0))))
        ul_cap_pct = min(99, max(10, int(round((ul_cap_raw / max_theoretical_kbps) * 100.0))))
    else:
        dl_cap_pct = dl_cap_raw
        ul_cap_pct = ul_cap_raw
    avg_cap_pct = int(round((dl_cap_pct + ul_cap_pct) / 2.0))

    cinr = int(float(kv.get("cinr") or 28))
    qual_pct = min(99, max(35, int(round((cinr / 32.0) * 100.0))))

    result: dict[str, Any] = {
        "mac_address": mac,
        "current_ip": ip_address,
        "wan_ip": kv.get("deviceIp"),
        "lan_ip": kv.get("lanIpAddress") or ip_address,
        "netrole": kv.get("netrole"),
        "hostname": kv.get("deviceName") or f"{model}-{mac[-5:].replace(':', '')}",
        "model": model,
        "product_code": code,
        "role": role,
        "ssid": kv.get("essid"),
        "firmware_version": kv.get("firmwareVersion") or "WA.v8.7.9",
        "frequency_mhz": freq_val,
        "channel_width_mhz": chan_bw,
        "tx_power_dbm": int(float(kv.get("txPower") or 25)),
        "noise_floor_dbm": int(float(kv.get("noise") or -92)),
        "cpu_load_pct": cpu_pct,
        "memory_used_pct": mem_pct,
        "uptime_sec": int(float(kv.get("uptime") or 0)),
        "gps_lat": lat,
        "gps_lon": lon,
        "status": "online",
    }

    if role == "station" and parent_ap_mac:
        sig = int(float(kv.get("signal") or -47))
        c0 = int(float(kv.get("chain0Signal") or sig))
        c1 = int(float(kv.get("chain1Signal") or sig))
        result["parent_ap_mac"] = parent_ap_mac
        result["station_link"] = {
            "client_mac": mac,
            "last_known_ip": ip_address,
            "remote_hostname": result["hostname"],
            "remote_model": model,
            "remote_firmware": result["firmware_version"],
            "is_connected": int(kv.get("wlanConnections") or 1) > 0,
            "signal_dbm": sig,
            "remote_signal_dbm": sig,
            "chain0_dbm": c0,
            "chain1_dbm": c1,
            "noise_floor_dbm": result["noise_floor_dbm"],
            "tx_rate_mbps": float(kv.get("wlanTxRate") or 173.3),
            "rx_rate_mbps": float(kv.get("wlanRxRate") or 173.3),
            "airmax_capacity_pct": avg_cap_pct,
            "airmax_quality_pct": qual_pct,
            "distance_meters": int(float(kv.get("distance") or 150)),
            "connection_uptime_sec": int(float(kv.get("wlanUptime") or result["uptime_sec"])),
            "tx_bytes": int(float(kv.get("wlanTxBytes") or 0)),
            "rx_bytes": int(float(kv.get("wlanRxBytes") or 0)),
            "tx_latency_ms": float(kv.get("wlanTxLatency") or 1.0),
        }

    return result


def run_airos_ssh_with_password(
    host_ip: str,
    username: str,
    password: str,
    remote_cmd: str,
    ssh_port: int = 22,
    timeout_sec: float = 10.0,
) -> str:
    """
    Executes a command on an airOS 8 radio over SSH using Python's built-in `pty` module
    to supply the password from the Web Dashboard Credential Vault (no `sshpass` needed).
    Automatically enables `+ssh-rsa` for airOS 8 Dropbear compatibility.
    """
    master_fd, slave_fd = pty.openpty()
    cmd = [
        "ssh",
        "-p",
        str(ssh_port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "HostKeyAlgorithms=+ssh-rsa",
        "-o",
        "PubkeyAcceptedAlgorithms=+ssh-rsa",
        "-o",
        "KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1",
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        f"ConnectTimeout={max(3, int(timeout_sec))}",
        f"{username}@{host_ip}",
        remote_cmd,
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave_fd)

    output_chunks: list[bytes] = []
    password_sent = False
    deadline = time.monotonic() + timeout_sec

    try:
        while time.monotonic() < deadline:
            rlist, _, _ = select.select([master_fd], [], [], 0.25)
            if master_fd in rlist:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output_chunks.append(chunk)
                combined = b"".join(output_chunks)
                if not password_sent and b"password:" in combined.lower():
                    os.write(master_fd, (password + "\n").encode("utf-8"))
                    password_sent = True
                    output_chunks.clear()
                elif password_sent and b"permission denied" in combined.lower():
                    raise RuntimeError(f"Authentication failed for '{username}@{host_ip}' (Permission denied)")
            elif proc.poll() is not None:
                break
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                proc.kill()

    raw_text = b"".join(output_chunks).decode("utf-8", errors="replace")
    # Strip leading newline echo after password submission
    cleaned_lines = [
        line
        for line in raw_text.splitlines()
        if not line.strip().lower().endswith("password:")
    ]
    result_text = "\n".join(cleaned_lines).strip()
    if not result_text and proc.returncode not in (0, None):
        raise RuntimeError(f"SSH connection to {host_ip}:{ssh_port} failed (exit {proc.returncode})")
    return result_text


class AirOS8Client:
    """
    HTTP/HTTPS & SSH Session Client for Ubiquiti airOS 8 radios (`LiteAP GPS` & `Loco 5AC`).
    Defaults to HTTP port 80 (or HTTPS 443) with automatic fallback between 80 and 443,
    plus native SSH (port 22) support for `mca-status`, `wstalist`, and `iwpriv ath0 kickmac`.
    """

    def __init__(
        self,
        host_ip: str,
        username: str = "ubnt",
        password: str = "ubnt",
        https_port: int = 80,
        use_https: bool | None = None,
        timeout_sec: float = 5.0,
    ) -> None:
        self.host_ip = host_ip
        self.username = username
        self.password = password
        self.https_port = https_port
        self.use_https = (https_port not in (80, 8080)) if use_https is None else use_https
        self.timeout_sec = timeout_sec
        scheme = "https" if self.use_https else "http"
        self.base_url = f"{scheme}://{host_ip}:{https_port}"
        self.csrf_token: str | None = None
        self.cookie_jar = CookieJar()

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = request.build_opener(
            request.HTTPSHandler(context=ssl_ctx),
            request.HTTPCookieProcessor(self.cookie_jar),
        )

    def _switch_to_http_fallback(self) -> None:
        self.use_https = False
        self.https_port = 80
        self.base_url = f"http://{self.host_ip}:80"

    def _request_json(
        self,
        method: str,
        path: str,
        form_data: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
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

        for attempt in range(2):
            url = f"{self.base_url}{path}"
            req = request.Request(url, data=data_bytes, headers=headers, method=method)
            try:
                with self._opener.open(req, timeout=self.timeout_sec) as resp:
                    csrf_hdr = resp.headers.get("X-CSRF-ID")
                    if csrf_hdr:
                        self.csrf_token = csrf_hdr
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except Exception as exc:
                # If HTTPS (443) is refused on the radio, automatically fall back to HTTP (80)
                if attempt == 0 and self.use_https and "Connection refused" in str(exc):
                    self._switch_to_http_fallback()
                    continue
                raise

    def login(self) -> bool:
        """
        Authenticates against airOS 8 web dashboard (`/api/auth` on lighttpd/1.4.54).
        First primes the session cookie via `GET /`, then submits `username` & `password`.
        """
        try:
            prime_req = request.Request(
                f"{self.base_url}/",
                headers={"User-Agent": "AirManager-Linux-Agent/1.0"},
                method="GET",
            )
            with self._opener.open(prime_req, timeout=self.timeout_sec) as prime_resp:
                csrf_hdr = prime_resp.headers.get("X-CSRF-ID")
                if csrf_hdr:
                    self.csrf_token = csrf_hdr
                _ = prime_resp.read(512)
        except Exception as exc:
            if self.use_https and "Connection refused" in str(exc):
                self._switch_to_http_fallback()
            # Proceed to POST /api/auth even if GET / returned redirect/error

        resp = self._request_json(
            "POST",
            "/api/auth",
            form_data={"username": self.username, "password": self.password},
        )
        if isinstance(resp, dict):
            tok = resp.get("csrf_token") or resp.get("utoken")
            if tok and not self.csrf_token:
                self.csrf_token = str(tok)
        return bool(resp is not None)

    def probe_via_ssh(
        self,
        ssh_port: int = 22,
        previous_counters: dict[str, tuple[float, int, int]] | None = None,
    ) -> dict[str, Any]:
        """
        Probes an airOS 8 radio (`WA.v8.7.x`) via SSH (`mca-status` + `wstalist`) using
        the `username` (`admin`) and `password` entered in the Web Dashboard.
        """
        combined_out = run_airos_ssh_with_password(
            host_ip=self.host_ip,
            username=self.username,
            password=self.password,
            remote_cmd='mca-status; echo "===AIRMANAGER_WSTALIST==="; wstalist',
            ssh_port=ssh_port,
            timeout_sec=max(8.0, self.timeout_sec),
        )
        parts = combined_out.split("===AIRMANAGER_WSTALIST===", 1)
        mca_part = parts[0].strip()
        wsta_part = parts[1].strip() if len(parts) > 1 else ""

        if "deviceId=" not in mca_part and "apMac=" not in mca_part and "platform=" not in mca_part:
            raise RuntimeError(f"Unexpected mca-status output from {self.host_ip}: {mca_part[:160]}")

        status_dict = parse_mca_status_output(self.host_ip, mca_part)

        # Parse wstalist JSON if present
        if wsta_part:
            json_start = wsta_part.find("[")
            json_end = wsta_part.rfind("]")
            if json_start != -1 and json_end != -1 and json_end >= json_start:
                try:
                    wsta_list = json.loads(wsta_part[json_start : json_end + 1])
                    if isinstance(wsta_list, list) and wsta_list:
                        if status_dict.get("role") == "ap":
                            status_dict["clients"] = parse_airos_sta_json(
                                wsta_list, previous_counters=previous_counters
                            )
                        elif status_dict.get("role") == "station":
                            ap_entry = wsta_list[0]
                            ap_remote = ap_entry.get("remote", {}) or {}
                            if ap_remote.get("hostname"):
                                status_dict["parent_ap_hostname"] = str(ap_remote["hostname"])
                            if ap_remote.get("ipaddr") or ap_entry.get("lastip"):
                                status_dict["parent_ap_ip"] = str(
                                    ap_remote.get("ipaddr") or ap_entry.get("lastip")
                                )
                            if ap_remote.get("platform"):
                                ap_model, _ = classify_airos_model(str(ap_remote["platform"]))
                                status_dict["parent_ap_model"] = ap_model
                except Exception:
                    pass

        if status_dict.get("clients"):
            status_dict["tx_throughput_kbps"] = sum(
                float(c.get("tx_throughput_kbps") or 0.0) for c in status_dict["clients"]
            )
            status_dict["rx_throughput_kbps"] = sum(
                float(c.get("rx_throughput_kbps") or 0.0) for c in status_dict["clients"]
            )
        return status_dict

    def probe_full_device(
        self, previous_counters: dict[str, tuple[float, int, int]] | None = None
    ) -> dict[str, Any]:
        """
        Probes an airOS 8 radio using the credentials from the Web Dashboard.
        Tries SSH (`mca-status` + `wstalist` on port 22) first for 100% compatibility with
        airOS 8.7.x (`WA.ar934x.v8.7.9`), and falls back to HTTP/HTTPS (`/api/auth` + `/status.cgi`) if SSH is closed.
        """
        ssh_error: Exception | None = None
        if self.password:
            try:
                return self.probe_via_ssh(ssh_port=22, previous_counters=previous_counters)
            except Exception as exc:
                ssh_error = exc

        try:
            self.login()
            status_dict = self.fetch_status()
            if status_dict.get("role") == "ap" and "clients" not in status_dict:
                try:
                    status_dict["clients"] = self.fetch_stations(previous_counters=previous_counters)
                except Exception:
                    status_dict.setdefault("clients", [])
            if status_dict.get("clients"):
                status_dict["tx_throughput_kbps"] = sum(
                    float(c.get("tx_throughput_kbps") or 0.0) for c in status_dict["clients"]
                )
                status_dict["rx_throughput_kbps"] = sum(
                    float(c.get("rx_throughput_kbps") or 0.0) for c in status_dict["clients"]
                )
            return status_dict
        except Exception as http_exc:
            if ssh_error is not None:
                raise RuntimeError(f"SSH probe error: {ssh_error}; HTTP probe error: {http_exc}") from http_exc
            raise

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

    async def run_ssh_command(self, remote_cmd: str, ssh_port: int = 22) -> str:
        """
        Executes an airOS 8 CLI command (`mca-status`, `wstalist`, `iwpriv ath0 kickmac <mac>`)
        over SSH, automatically enabling `+ssh-rsa` for airOS 8 Dropbear compatibility on Ubuntu 22.04/24.04.
        """
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "HostKeyAlgorithms=+ssh-rsa",
            "-o",
            "PubkeyAcceptedAlgorithms=+ssh-rsa",
            "-o",
            f"ConnectTimeout={int(self.timeout_sec)}",
            "-p",
            str(ssh_port),
            f"{self.username}@{self.host_ip}",
            remote_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_sec + 2.0)
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"airOS SSH failed ({proc.returncode}): {err}")
        return stdout.decode("utf-8", errors="replace")

