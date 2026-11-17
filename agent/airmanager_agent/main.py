from __future__ import annotations

"""
AirManager Linux Network Agent Daemon Entrypoint.
Run via systemd (`airmanager-agent.service`):
    python3 -m airmanager_agent.main
"""

import asyncio
import logging
import socket

from airmanager_agent.config import agent_config
from airmanager_agent.poller.scheduler import AgentScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] airmanager-agent: %(message)s",
)
logger = logging.getLogger("airmanager_agent")


async def run_agent_forever() -> None:
    scheduler = AgentScheduler(agent_config)
    logger.info(
        "Starting AirManager Linux Agent (%s) -> Backend %s",
        agent_config.agent_id,
        agent_config.backend_url,
    )

    while True:
        try:
            hb = scheduler.backend.post_json(
                "/api/v1/agent/heartbeat",
                {
                    "agent_id": agent_config.agent_id,
                    "hostname": socket.gethostname(),
                    "version": "1.0.0",
                    "active_workers": agent_config.scan_concurrency,
                    "simulator_mode": agent_config.simulator_mode,
                },
            )
            for task in hb.get("pending_tasks", []):
                task_id = task["id"]
                try:
                    res = await scheduler.execute_task(task)
                    scheduler.backend.post_json(
                        f"/api/v1/agent/tasks/{task_id}/result",
                        {"status": "completed", "result": res},
                    )
                except Exception as task_exc:
                    scheduler.backend.post_json(
                        f"/api/v1/agent/tasks/{task_id}/result",
                        {"status": "failed", "error_message": str(task_exc)},
                    )
        except Exception as exc:
            logger.warning("Heartbeat cycle error: %s", exc)

        await asyncio.sleep(agent_config.poll_interval_sec)


if __name__ == "__main__":
    asyncio.run(run_agent_forever())
