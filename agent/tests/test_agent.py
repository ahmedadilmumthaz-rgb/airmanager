from __future__ import annotations

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from airmanager_agent.airos.client import (
    parse_airos_sta_json,
    parse_airos_status_json,
    parse_mca_status_output,
    update_system_cfg_mac_acl,
)
from airmanager_agent.airos.simulator import (
    generate_simulated_airos_sta_list,
    generate_simulated_airos_status,
)
from airmanager_agent.config import AgentConfig
from airmanager_agent.poller.scheduler import AgentScheduler
from airmanager_agent.routers.ubiquiti import (
    parse_edgeos_arp_table,
    parse_edgeos_dhcp_leases,
    parse_uisp_arp_payload,
)
from airmanager_agent.scanner.cidr_scanner import RoutedSubnetScanner, expand_cidr_hosts


class TestAirManagerLinuxAgent(unittest.TestCase):
    def test_cidr_expansion_and_routed_subnet_scanner(self) -> None:
        hosts = expand_cidr_hosts("10.10.10.0/29")
        self.assertEqual(len(hosts), 6)
        self.assertEqual(hosts[0], "10.10.10.1")
        self.assertEqual(hosts[-1], "10.10.10.6")

        async def mock_prober(ip_str: str, port: int, timeout: float) -> float | None:
            if ip_str in ("10.10.10.2", "10.10.10.5") and port == 443:
                return 1.8
            return None

        scanner = RoutedSubnetScanner(concurrency=16, timeout_sec=0.5, custom_prober=mock_prober)
        results = asyncio.run(scanner.scan_cidr("10.10.10.0/29"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].ip_address, "10.10.10.2")
        self.assertEqual(results[1].ip_address, "10.10.10.5")
        self.assertEqual(results[0].open_port, 443)

    def test_airos8_status_and_station_parsing(self) -> None:
        raw_status = generate_simulated_airos_status(
            ip_address="10.10.10.11",
            mac_address="78:8a:20:41:10:01",
            hostname="LAP-North-Sector-Alpha",
            model="LiteAP GPS",
        )
        parsed_dev = parse_airos_status_json("10.10.10.11", raw_status)
        self.assertEqual(parsed_dev["mac_address"], "78:8A:20:41:10:01")
        self.assertEqual(parsed_dev["model"], "LiteAP GPS")
        self.assertEqual(parsed_dev["role"], "ap")
        self.assertEqual(parsed_dev["frequency_mhz"], 5745)

        counters: dict[str, tuple[float, int, int]] = {}
        raw_sta = generate_simulated_airos_sta_list(subnet_prefix="10.10.10", count=5)
        parsed_sta = parse_airos_sta_json(raw_sta, previous_counters=counters)
        self.assertEqual(len(parsed_sta), 5)
        self.assertEqual(parsed_sta[0]["remote_model"], "Loco 5AC")
        self.assertEqual(parsed_sta[0]["last_known_ip"], "10.10.10.101")

    def test_airos8_mac_acl_cfg_manipulation(self) -> None:
        initial_cfg = "wireless.1.status=enabled\nwireless.1.ssid=WISP-5G\n"
        blocked_cfg = update_system_cfg_mac_acl(initial_cfg, "78:8a:20:91:0a:01", block=True)
        self.assertIn("wireless.1.mac_acl.status=enabled", blocked_cfg)
        self.assertIn("wireless.1.mac_acl.1.mac=78:8A:20:91:0A:01", blocked_cfg)

        unblocked_cfg = update_system_cfg_mac_acl(blocked_cfg, "78:8A:20:91:0A:01", block=False)
        self.assertIn("wireless.1.mac_acl.status=disabled", unblocked_cfg)
        self.assertNotIn("78:8A:20:91:0A:01", unblocked_cfg)

    def test_ubiquiti_router_arp_and_dhcp_enrichment(self) -> None:
        sample_arp = """
Address                  HWtype  HWaddress           Flags Mask            Iface
10.10.10.11              ether   78:8a:20:41:10:01   C                     eth1.110
10.10.20.105             ether   fc:ec:da:11:22:33   C                     eth1.120
192.168.1.50             ether   00:11:22:33:44:55   C                     eth0
"""
        arp_entries = parse_edgeos_arp_table(sample_arp, ubiquiti_only=True)
        self.assertEqual(len(arp_entries), 2)
        self.assertEqual(arp_entries[0].mac_address, "78:8A:20:41:10:01")
        self.assertEqual(arp_entries[1].mac_address, "FC:EC:DA:11:22:33")

        sample_dhcp = """
IP address      Hardware Address   Lease expiration     Pool       Client Name
----------      ----------------   ----------------     ----       -----------
172.16.40.108   78:8a:20:93:0e:15  2026/11/18 12:00:00  VLAN240    Loco5AC-Valley8
"""
        dhcp_entries = parse_edgeos_dhcp_leases(sample_dhcp, ubiquiti_only=True)
        self.assertEqual(len(dhcp_entries), 1)
        self.assertEqual(dhcp_entries[0].ip_address, "172.16.40.108")
        self.assertEqual(dhcp_entries[0].hostname, "Loco5AC-Valley8")

        uisp_entries = parse_uisp_arp_payload(
            [{"mac": "80:2a:a8:55:66:77", "ip": "10.10.10.199", "interface": "br0"}],
            ubiquiti_only=True,
        )
        self.assertEqual(len(uisp_entries), 1)
        self.assertEqual(uisp_entries[0].mac_address, "80:2A:A8:55:66:77")

    def test_agent_scheduler_simulator_and_task_execution(self) -> None:
        cfg = AgentConfig(simulator_mode=True)
        scheduler = AgentScheduler(config=cfg)
        cycle_data = scheduler.collect_simulator_cycle()
        self.assertEqual(len(cycle_data), 1)
        self.assertEqual(len(cycle_data[0]["clients"]), 6)

        res = asyncio.run(
            scheduler.execute_task(
                {
                    "task_type": "block_client",
                    "payload": {"client_mac": "78:8A:20:91:0A:01"},
                }
            )
        )
        self.assertEqual(res["action"], "block_client")

    def test_real_nel1006_loco5ac_mca_status_parsing(self) -> None:
        real_mca = """deviceName=NEL1006,deviceId=E0:63:DA:F2:A1:B9,firmwareVersion=WA.ar934x.v8.7.9.46843.220329.1728,platform=NanoStation 5AC loco,deviceIp=10.42.200.187

apMac=18:E8:29:8E:B2:AC
wlanOpmode=sta-ptmp-ac
wlanConnections=1
wlanUptime=213415
essid=BUDDIESNET6
security=WPA2
freq=5665
centerFreq=5665
txPower=25
chanbw=20
signal=-47
chain0Signal=-49
chain1Signal=-51
noise=-92
cinr=29
evm=28
uptime=213507
airTime=0.6
cpuUsage=10.9
loadavg=1
memTotal=61960
memFree=14976
memBuffers=4704
distance=150
netrole=router
lanIpAddress=10.61.200.185
wlanIpAddress=0.0.0.0
wlanTxRate=173.3
wlanRxRate=173.3
wlanDownlinkCapacity=146640
wlanUplinkCapacity=143520
wlanRxBytes=71157516629
wlanTxBytes=3621414189
"""
        parsed = parse_mca_status_output("10.61.200.185", real_mca)
        self.assertEqual(parsed["hostname"], "NEL1006")
        self.assertEqual(parsed["mac_address"], "E0:63:DA:F2:A1:B9")
        self.assertEqual(parsed["parent_ap_mac"], "18:E8:29:8E:B2:AC")
        self.assertEqual(parsed["model"], "Loco 5AC")
        self.assertEqual(parsed["role"], "station")
        self.assertEqual(parsed["ssid"], "BUDDIESNET6")
        self.assertEqual(parsed["frequency_mhz"], 5665)
        self.assertEqual(parsed["channel_width_mhz"], 20)
        self.assertEqual(parsed["wan_ip"], "10.42.200.187")
        self.assertEqual(parsed["lan_ip"], "10.61.200.185")
        self.assertEqual(parsed["station_link"]["signal_dbm"], -47)
        self.assertEqual(parsed["station_link"]["chain0_dbm"], -49)
        self.assertEqual(parsed["station_link"]["chain1_dbm"], -51)
        self.assertEqual(parsed["station_link"]["distance_meters"], 150)



if __name__ == "__main__":
    unittest.main()
