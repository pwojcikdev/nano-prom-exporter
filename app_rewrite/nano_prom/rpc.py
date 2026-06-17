"""nano_node RPC client.

Each metric collection cycle issues one POST per command and records its
latency. The raw JSON responses are returned untouched; parsing happens in
:mod:`nano_prom.stats`.
"""

from __future__ import annotations

import requests

# Maps our internal stat name -> the RPC request body.
# confirmation_history is intentionally omitted: it is a slow call on the node.
COMMANDS = {
    "version": {"action": "version"},
    "block_count": {"action": "block_count"},
    "peers": {"action": "peers"},
    "stats_counters": {"action": "stats", "type": "counters"},
    "stats_objects": {"action": "stats", "type": "objects"},
    "uptime": {"action": "uptime"},
    "active_difficulty": {"action": "active_difficulty"},
    "frontier_count": {"action": "frontier_count"},
    "confirmation_quorum": {"action": "confirmation_quorum"},
    "telemetry_raw": {"action": "telemetry", "raw": "true"},
    "telemetry": {"action": "telemetry"},
}


class NanoRpcClient:
    def __init__(self, host: str, port: str, timeout: int = 7):
        self.url = f"http://{host}:{port}"
        self.timeout = timeout

    def call(self, payload: dict) -> dict:
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        return response.json()

    def gather(self, latency) -> dict:
        """Run every command and return ``{name: response}``.

        ``latency`` is a Prometheus Histogram labelled by ``method``; each call
        is timed into it.
        """
        raw = {}
        for name, payload in COMMANDS.items():
            with latency.labels(name).time():
                raw[name] = self.call(payload)
        return raw
