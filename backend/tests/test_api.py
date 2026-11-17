from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret
from app.db.repository import AirManagerRepository
from app.services.dispatcher import AirManagerDispatcher


class TestAirManagerBackend(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.repo = AirManagerRepository(db_path_or_url=f"sqlite:///{self.tmp_db.name}")
        self.dispatcher = AirManagerDispatcher(repo=self.repo, auto_seed=True)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db.name):
            os.unlink(self.tmp_db.name)

    def test_credential_encryption_roundtrip(self) -> None:
        secret = "SuperSecret-airOS8-Pass#2026"
        token = encrypt_secret(secret)
        self.assertNotIn(b"SuperSecret", token)
        recovered = decrypt_secret(token)
        self.assertEqual(recovered, secret)

    def test_seeded_dashboard_and_multi_subnet_topology(self) -> None:
        code, data = self.dispatcher.handle_request("GET", "/api/v1/dashboard/summary")
        self.assertEqual(code, 200)
        assert isinstance(data, dict)
        kpis = data["kpis"]
        self.assertEqual(kpis["total_aps"], 4)
        self.assertEqual(kpis["total_clients"], 36)
        self.assertEqual(kpis["routed_subnets_count"], 3)
        self.assertEqual(kpis["routers_count"], 2)
        self.assertGreaterEqual(kpis["weak_signal_count"], 4)
        self.assertGreaterEqual(kpis["chain_imbalance_count"], 4)

    def test_mac_based_ip_reconciliation_and_history(self) -> None:
        mac = "78:8A:20:AA:BB:CC"
        # First discovery at 10.10.10.55
        res1 = self.repo.upsert_discovered_device(
            {
                "mac_address": mac,
                "current_ip": "10.10.10.55",
                "hostname": "Loco5AC-Test-Migration",
                "model": "Loco 5AC",
                "role": "station",
                "discovery_source": "subnet_scan",
            }
        )
        self.assertFalse(res1["ip_changed"])

        # Radio moves to 10.10.20.88 via DHCP/routed subnet change
        res2 = self.repo.upsert_discovered_device(
            {
                "mac_address": mac,
                "current_ip": "10.10.20.88",
                "hostname": "Loco5AC-Test-Migration",
                "model": "Loco 5AC",
                "role": "station",
                "discovery_source": "router_dhcp",
            }
        )
        self.assertTrue(res2["ip_changed"])
        self.assertEqual(res2["previous_ip"], "10.10.10.55")
        self.assertEqual(res2["current_ip"], "10.10.20.88")
        self.assertEqual(res1["device_id"], res2["device_id"])

        detail = self.repo.get_device_detail(res1["device_id"])
        assert detail is not None
        self.assertEqual(len(detail["ip_history"]), 2)
        ips = [h["ip_address"] for h in detail["ip_history"]]
        self.assertIn("10.10.10.55", ips)
        self.assertIn("10.10.20.88", ips)

    def test_connected_client_filters_and_management_actions(self) -> None:
        # Filter weak signal clients
        code, weak_resp = self.dispatcher.handle_request("GET", "/api/v1/clients?health_filter=weak_signal")
        self.assertEqual(code, 200)
        assert isinstance(weak_resp, dict)
        self.assertGreater(weak_resp["total"], 0)
        target_client = weak_resp["items"][0]
        client_id = target_client["id"]

        # 1. Kick / Reconnect station
        code, kick_resp = self.dispatcher.handle_request("POST", f"/api/v1/clients/{client_id}/kick")
        self.assertEqual(code, 200)
        assert isinstance(kick_resp, dict)
        self.assertEqual(kick_resp["task"]["task_type"], "kick_client")
        self.assertEqual(kick_resp["client"]["connection_uptime_sec"], 5)

        # 2. Block station MAC via ACL
        code, block_resp = self.dispatcher.handle_request(
            "POST", f"/api/v1/clients/{client_id}/acl", body={"action": "block"}
        )
        self.assertEqual(code, 200)
        assert isinstance(block_resp, dict)
        self.assertTrue(block_resp["client"]["is_blocked"])
        self.assertFalse(block_resp["client"]["is_connected"])

        # 3. Unblock station MAC
        code, unblock_resp = self.dispatcher.handle_request(
            "POST", f"/api/v1/clients/{client_id}/acl", body={"action": "unblock"}
        )
        self.assertEqual(code, 200)
        assert isinstance(unblock_resp, dict)
        self.assertFalse(unblock_resp["client"]["is_blocked"])
        self.assertTrue(unblock_resp["client"]["is_connected"])

        # 4. Reboot remote Loco 5AC
        code, reboot_resp = self.dispatcher.handle_request("POST", f"/api/v1/clients/{client_id}/reboot")
        self.assertEqual(code, 200)
        assert isinstance(reboot_resp, dict)
        self.assertEqual(reboot_resp["task"]["task_type"], "reboot_device")

    def test_agent_protocol_authentication_and_telemetry_ingestion(self) -> None:
        # Reject unauthorized agent call
        code, _ = self.dispatcher.handle_request(
            "POST",
            "/api/v1/agent/heartbeat",
            body={"agent_id": "test-agent"},
            headers={"x-agent-token": "wrong-token"},
        )
        self.assertEqual(code, 401)

        # Accept authorized heartbeat
        code, hb = self.dispatcher.handle_request(
            "POST",
            "/api/v1/agent/heartbeat",
            body={"agent_id": "ubuntu-agent-1"},
            headers={"x-agent-token": settings.agent_token},
        )
        self.assertEqual(code, 200)
        assert isinstance(hb, dict)
        self.assertEqual(len(hb["subnets"]), 3)

        # Ingest telemetry report from agent
        code, rep = self.dispatcher.handle_request(
            "POST",
            "/api/v1/agent/telemetry-report",
            body={
                "devices": [
                    {
                        "mac_address": "78:8A:20:41:10:01",
                        "current_ip": "10.10.10.11",
                        "hostname": "LAP-North-Sector-Alpha",
                        "model": "LiteAP GPS",
                        "role": "ap",
                        "tx_throughput_kbps": 75100.0,
                        "rx_throughput_kbps": 21200.0,
                    }
                ]
            },
            headers={"x-agent-token": settings.agent_token},
        )
        self.assertEqual(code, 200)
        assert isinstance(rep, dict)
        self.assertEqual(rep["processed"], 1)


if __name__ == "__main__":
    unittest.main()
