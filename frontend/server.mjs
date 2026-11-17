/**
 * AirManager Standalone Operator Console Server (Zero External Node Dependencies)
 * Proxies /api/v1/* to the Python backend (127.0.0.1:8000) and serves the interactive
 * Connected Client & Multi-Subnet Management UI on http://127.0.0.1:3000.
 */

import http from "node:http";

const PORT = Number(process.env.PORT || 3000);
const API_HOST = process.env.API_HOST || "127.0.0.1";
const API_PORT = Number(process.env.API_PORT || 8000);

const HTML_DOCUMENT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AirManager — Ubiquiti airOS 8 Network Manager</title>
  <style>
    :root {
      --bg: #020617;
      --panel: #0f172a;
      --border: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --blue: #2563eb;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #e11d48;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }
    aside { width: 250px; background: var(--panel); border-right: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; justify-content: space-between; }
    main { flex: 1; padding: 28px; overflow-y: auto; }
    .brand { display: flex; align-items: center; gap: 10px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    .logo { width: 34px; height: 34px; border-radius: 8px; background: var(--blue); display: flex; align-items: center; justify-content: center; font-weight: 700; }
    nav { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
    nav button { background: transparent; color: var(--muted); border: none; text-align: left; padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; }
    nav button.active, nav button:hover { background: var(--blue); color: #fff; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin: 18px 0; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 18px; }
    .kpi-val { font-size: 24px; font-weight: 700; margin-top: 6px; }
    .kpi-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; }
    th { font-size: 11px; text-transform: uppercase; color: var(--muted); }
    .badge { padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; display: inline-block; }
    .good { background: rgba(16,185,129,0.18); color: #34d399; }
    .warn { background: rgba(245,158,11,0.18); color: #fbbf24; }
    .crit { background: rgba(225,29,72,0.22); color: #fda4af; }
    .btn { padding: 6px 11px; border-radius: 6px; border: 1px solid var(--border); background: #1e293b; color: #fff; cursor: pointer; font-size: 12px; margin-right: 4px; }
    .btn-primary { background: var(--blue); border-color: var(--blue); }
    .btn-danger { background: var(--rose); border-color: var(--rose); }
    .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }
    input, select { background: #020617; border: 1px solid var(--border); color: #fff; padding: 8px 12px; border-radius: 8px; font-size: 13px; }
    #banner { display: none; background: rgba(37,99,235,0.25); border: 1px solid var(--blue); padding: 10px 14px; border-radius: 8px; margin-bottom: 14px; font-size: 13px; }
  </style>
</head>
<body>
  <aside>
    <div>
      <div class="brand">
        <div class="logo">U</div>
        <div>
          <div style="font-weight:700;font-size:15px;">AirManager</div>
          <div style="font-size:11px;color:#94a3b8;">airOS 8 · Routed Subnets</div>
        </div>
      </div>
      <nav>
        <button id="tab-clients" class="active" onclick="switchView('clients')">Connected Clients (Loco 5AC)</button>
        <button id="tab-dashboard" onclick="switchView('dashboard')">Overview &amp; Sectors</button>
        <button id="tab-discovery" onclick="switchView('discovery')">Subnets &amp; Ubiquiti Routers</button>
        <button id="tab-tasks" onclick="switchView('tasks')">Agent Audit Log</button>
      </nav>
    </div>
    <div style="font-size:11px;color:#94a3b8;border-top:1px solid #1e293b;padding-top:12px;">
      <div style="color:#34d399;font-weight:600;">● Linux Routed Agent Online</div>
      <div style="margin-top:4px;">LiteAP GPS &amp; Loco 5AC</div>
    </div>
  </aside>
  <main>
    <div id="banner"></div>
    <div id="view-container">Loading AirManager...</div>
  </main>
  <script>
    let currentView = 'clients';
    let currentFilter = 'all';
    let searchQuery = '';

    function showBanner(msg) {
      const el = document.getElementById('banner');
      el.textContent = msg;
      el.style.display = 'block';
      setTimeout(() => { el.style.display = 'none'; }, 5000);
    }

    function switchView(view) {
      currentView = view;
      for (const id of ['clients', 'dashboard', 'discovery', 'tasks']) {
        document.getElementById('tab-' + id).className = (id === view) ? 'active' : '';
      }
      render();
    }

    async function clientAction(id, action, body) {
      const res = await fetch('/api/v1/clients/' + id + '/' + action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined
      });
      const data = await res.json();
      showBanner(data.message || 'Action completed');
      render();
    }

    async function simulateDrift() {
      const res = await fetch('/api/v1/discovery/simulate-ip-drift', { method: 'POST' });
      const data = await res.json();
      showBanner(data.message);
      render();
    }

    async function probeLiveRadio() {
      const ip = document.getElementById('probe-ip').value.trim();
      const user = document.getElementById('probe-user').value.trim() || 'admin';
      const pass = document.getElementById('probe-pass').value;
      const port = Number(document.getElementById('probe-port').value || 80);
      showBanner('Logging into http://' + ip + ':' + port + '/api/auth as ' + user + '...');
      const res = await fetch('/api/v1/discovery/probe-ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip_address: ip, username: user, password: pass, port: port, save_credential: true })
      });
      const data = await res.json();
      showBanner(data.message || data.detail || 'Probe completed');
      render();
    }

    async function saveDefaultCred() {
      const user = document.getElementById('probe-user').value.trim() || 'admin';
      const pass = document.getElementById('probe-pass').value;
      const port = Number(document.getElementById('probe-port').value || 80);
      const res = await fetch('/api/v1/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'WISP-Standard-airOS8', username: user, password: pass, https_port: port, is_default: true })
      });
      if (res.ok) showBanner('Saved default airOS 8 web login (' + user + ' on port ' + port + ')');
      render();
    }

    async function addSubnet() {
      const cidr = document.getElementById('new-cidr').value.trim();
      const name = document.getElementById('new-cidr-name').value.trim() || 'Production Radio Subnet';
      const res = await fetch('/api/v1/subnets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cidr_block: cidr, name: name })
      });
      const data = await res.json();
      showBanner(res.ok ? ('Added subnet ' + cidr) : (data.detail || 'Failed'));
      render();
    }

    async function scanSubnet(id) {
      showBanner('Scanning subnet via HTTP/HTTPS...');
      const res = await fetch('/api/v1/subnets/' + id + '/scan', { method: 'POST' });
      const data = await res.json();
      showBanner(data.message || data.detail);
      render();
    }

    async function clearDemo() {
      const res = await fetch('/api/v1/discovery/clear-devices', { method: 'POST' });
      const data = await res.json();
      showBanner(data.message);
      render();
    }

    async function render() {
      const container = document.getElementById('view-container');
      if (currentView === 'clients') {
        const res = await fetch('/api/v1/clients?health_filter=' + currentFilter + '&search=' + encodeURIComponent(searchQuery));
        const data = await res.json();
        const rows = data.items.map(c => {
          const sigClass = c.is_blocked ? 'crit' : (c.signal_dbm < -74 ? 'crit' : (c.signal_dbm < -68 ? 'warn' : 'good'));
          return '<tr>' +
            '<td><strong>' + c.remote_hostname + '</strong><br><span style="font-family:monospace;font-size:11px;color:#94a3b8">' + c.client_mac + ' · ' + (c.last_known_ip || '') + '</span></td>' +
            '<td>' + c.ap_hostname + '<br><span style="font-size:11px;color:#94a3b8">' + c.ap_ip + ' · ' + c.ap_ssid + '</span></td>' +
            '<td><span class="badge ' + sigClass + '">' + (c.is_blocked ? 'BLOCKED' : c.signal_dbm + ' dBm') + '</span> <span style="font-size:11px;color:#94a3b8">Ch0:' + c.chain0_dbm + '/Ch1:' + c.chain1_dbm + ' (Δ' + c.chain_imbalance_db + 'dB)</span></td>' +
            '<td>' + c.airmax_capacity_pct + '% Cap / ' + c.airmax_quality_pct + '% Qual</td>' +
            '<td>↓ ' + (c.tx_throughput_kbps/1000).toFixed(1) + ' Mbps / ↑ ' + (c.rx_throughput_kbps/1000).toFixed(1) + ' Mbps</td>' +
            '<td>' +
              '<button class="btn btn-primary" onclick="clientAction(\\'' + c.id + '\\', \\'kick\\')">Kick</button>' +
              '<button class="btn ' + (c.is_blocked ? '' : 'btn-danger') + '" onclick="clientAction(\\'' + c.id + '\\', \\'acl\\', {action:\\'' + (c.is_blocked ? 'unblock' : 'block') + '\\'})">' + (c.is_blocked ? 'Unblock' : 'Block') + '</button>' +
              '<button class="btn" onclick="clientAction(\\'' + c.id + '\\', \\'reboot\\')">Reboot</button>' +
            '</td></tr>';
        }).join('');
        container.innerHTML =
          '<h1 style="font-size:22px;margin-bottom:6px">Connected Client Management (NanoStation Loco 5AC)</h1>' +
          '<p style="color:#94a3b8;font-size:13px;margin-bottom:16px">Real-time airOS 8 station table across routed LiteAP GPS sectors</p>' +
          '<div class="toolbar">' +
            '<input placeholder="Search hostname, MAC, IP..." value="' + searchQuery + '" oninput="searchQuery=this.value;render()" />' +
            '<button class="btn ' + (currentFilter==='all'?'btn-primary':'') + '" onclick="currentFilter=\\'all\\';render()">All (' + data.total + ')</button>' +
            '<button class="btn ' + (currentFilter==='weak_signal'?'btn-primary':'') + '" onclick="currentFilter=\\'weak_signal\\';render()">Weak Signal</button>' +
            '<button class="btn ' + (currentFilter==='chain_imbalance'?'btn-primary':'') + '" onclick="currentFilter=\\'chain_imbalance\\';render()">Chain Imbalance ≥5dB</button>' +
            '<button class="btn ' + (currentFilter==='blocked'?'btn-primary':'') + '" onclick="currentFilter=\\'blocked\\';render()">Blocked MACs</button>' +
          '</div>' +
          '<div class="card"><table><thead><tr><th>Station CPE</th><th>Parent LiteAP GPS</th><th>Signal &amp; Chains</th><th>airMAX</th><th>Throughput</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
      } else if (currentView === 'dashboard') {
        const res = await fetch('/api/v1/dashboard/summary');
        const s = await res.json();
        const k = s.kpis;
        container.innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center">' +
            '<h1>Multi-Subnet Network Overview</h1>' +
            '<button class="btn btn-primary" onclick="simulateDrift()">Simulate DHCP/Routed IP Change</button>' +
          '</div>' +
          '<div class="kpis">' +
            '<div class="card"><div>Connected Clients</div><div class="kpi-val">' + k.connected_clients + ' / ' + k.total_clients + '</div><div class="kpi-sub">↓ ' + k.aggregate_tx_mbps + ' Mbps · ↑ ' + k.aggregate_rx_mbps + ' Mbps</div></div>' +
            '<div class="card"><div>LiteAP GPS Sectors</div><div class="kpi-val">' + k.total_aps + '</div><div class="kpi-sub">' + k.routed_subnets_count + ' Routed Subnets</div></div>' +
            '<div class="card"><div>Signal / Chain Alerts</div><div class="kpi-val" style="color:#fbbf24">' + k.weak_signal_count + ' Weak · ' + k.chain_imbalance_count + ' ΔChain</div><div class="kpi-sub">' + k.low_capacity_count + ' low capacity</div></div>' +
            '<div class="card"><div>Ubiquiti Routers</div><div class="kpi-val">' + k.routers_count + '</div><div class="kpi-sub">EdgeRouter &amp; UISP ARP/DHCP</div></div>' +
          '</div>' +
          '<div class="card"><h3 style="margin-bottom:10px">Canonical MAC Identity — Recent IP History</h3><table><thead><tr><th>Hostname</th><th>MAC Identity</th><th>Observed IP</th><th>Discovery Source</th></tr></thead><tbody>' +
            s.recent_ip_history.map(h => '<tr><td>' + h.hostname + '</td><td style="font-family:monospace">' + h.mac_address + '</td><td style="font-family:monospace;color:#60a5fa">' + h.ip_address + '</td><td>' + h.discovery_source + '</td></tr>').join('') +
          '</tbody></table></div>';
      } else if (currentView === 'discovery') {
        const [subRes, rtrRes, credRes] = await Promise.all([
          fetch('/api/v1/subnets'),
          fetch('/api/v1/routers'),
          fetch('/api/v1/credentials')
        ]);
        const subs = await subRes.json();
        const rtrs = await rtrRes.json();
        const creds = await credRes.json();
        container.innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">' +
            '<h1>airOS 8 Web Login (admin) &amp; Routed Subnet Discovery</h1>' +
            '<button class="btn btn-danger" onclick="clearDemo()">Clear Demo Radios</button>' +
          '</div>' +
          '<div class="card" style="border-color:#2563eb">' +
            '<h3 style="margin-bottom:8px">1. Live airOS 8 Web Dashboard Login &amp; Radio Probe (HTTP Port 80)</h3>' +
            '<p style="font-size:12px;color:#94a3b8;margin-bottom:12px">Authenticates via <code>POST /api/auth</code> using username <code>admin</code>, saves the encrypted credential profile, and imports <code>/status.cgi</code> &amp; <code>/sta.cgi</code>.</p>' +
            '<div class="toolbar">' +
              '<input id="probe-ip" value="10.61.200.185" placeholder="Radio IP (e.g. 10.61.200.185)" />' +
              '<input id="probe-user" value="admin" placeholder="Username (admin)" style="width:120px" />' +
              '<input id="probe-pass" type="password" placeholder="Web Login Password..." />' +
              '<input id="probe-port" type="number" value="80" style="width:85px" />' +
              '<button class="btn btn-primary" onclick="probeLiveRadio()">Login &amp; Probe Radio</button>' +
              '<button class="btn" onclick="saveDefaultCred()">Save Default Login</button>' +
            '</div>' +
          '</div>' +
          '<div class="card">' +
            '<h3 style="margin-bottom:10px">2. Configured Routed Subnets (CIDR)</h3>' +
            '<div class="toolbar">' +
              '<input id="new-cidr" value="10.61.200.0/24" placeholder="10.61.200.0/24" />' +
              '<input id="new-cidr-name" value="Production airOS 8 Subnet" placeholder="Subnet Name" style="width:240px" />' +
              '<button class="btn btn-primary" onclick="addSubnet()">+ Add Routed CIDR</button>' +
            '</div>' +
            '<table><thead><tr><th>CIDR Block</th><th>Name</th><th>VLAN</th><th>Discovered Radios</th><th>Action</th></tr></thead><tbody>' +
            subs.items.map(s => '<tr><td style="font-family:monospace;color:#60a5fa">' + s.cidr_block + '</td><td>' + s.name + '</td><td>' + (s.vlan_id || '—') + '</td><td>' + s.device_count + '</td><td><button class="btn btn-primary" onclick="scanSubnet(\\'' + s.id + '\\')">Scan Subnet Now</button></td></tr>').join('') +
          '</tbody></table></div>' +
          '<div class="card"><h3 style="margin-bottom:10px">3. Saved Credential Profiles (Encrypted Vault)</h3><table><thead><tr><th>Profile Name</th><th>Web Username</th><th>Port</th><th>Status</th></tr></thead><tbody>' +
            creds.items.map(c => '<tr><td>' + c.name + '</td><td style="font-family:monospace">' + c.username + '</td><td>' + c.https_port + '</td><td>' + (c.is_default ? '<span class="badge good">Default</span>' : '') + '</td></tr>').join('') +
          '</tbody></table></div>' +
          '<div class="card"><h3 style="margin-bottom:10px">4. Ubiquiti Routers (ARP / DHCP Enrichment)</h3><table><thead><tr><th>Router Name</th><th>Host IP</th><th>Platform</th><th>Neighbors</th><th>Status</th></tr></thead><tbody>' +
            rtrs.items.map(r => '<tr><td>' + r.name + '</td><td style="font-family:monospace">' + r.host_ip + '</td><td>' + r.router_type.toUpperCase() + '</td><td>' + r.neighbors_found + '</td><td>' + r.last_sync_status + '</td></tr>').join('') +
          '</tbody></table></div>';
      } else {
        const res = await fetch('/api/v1/tasks');
        const tData = await res.json();
        container.innerHTML =
          '<h1 style="margin-bottom:14px">Agent Task Queue &amp; Audit Log</h1>' +
          '<div class="card"><table><thead><tr><th>Task Type</th><th>Target</th><th>Status</th><th>Result</th><th>Time</th></tr></thead><tbody>' +
            tData.items.map(t => '<tr><td style="font-family:monospace;color:#60a5fa">' + t.task_type + '</td><td>' + (t.client_hostname || t.device_hostname || 'Subnet') + '</td><td><span class="badge good">' + t.status + '</span></td><td style="font-family:monospace;font-size:11px">' + JSON.stringify(t.result || t.payload) + '</td><td>' + new Date(t.created_at).toLocaleTimeString() + '</td></tr>').join('') +
          '</tbody></table></div>';
      }
    }
    render();
  </script>
</body>
</html>`;

const server = http.createServer((req, res) => {
  if (req.url && req.url.startsWith("/api/v1")) {
    const proxyReq = http.request(
      {
        hostname: API_HOST,
        port: API_PORT,
        path: req.url,
        method: req.method,
        headers: req.headers,
      },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
        proxyRes.pipe(res, { end: true });
      }
    );
    proxyReq.on("error", (err) => {
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: `Backend proxy error: ${err.message}` }));
    });
    req.pipe(proxyReq, { end: true });
    return;
  }

  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(HTML_DOCUMENT);
});

if (process.argv[1] && process.argv[1].endsWith("server.mjs")) {
  server.listen(PORT, "127.0.0.1", () => {
    console.log(`AirManager Frontend running on http://127.0.0.1:${PORT}`);
  });
}

export { server };
