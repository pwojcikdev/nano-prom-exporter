from prometheus_client import CollectorRegistry

import nano_prom.rpc as rpc_module
from nano_prom.metrics import Metrics
from nano_prom.rpc import COMMANDS, NanoRpcClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_gather_runs_every_command(monkeypatch, sample_raw):
    def fake_post(url, json, timeout):
        action = json["action"]
        if action == "stats":
            key = (
                "stats_counters" if json.get("type") == "counters" else "stats_objects"
            )
        elif action == "telemetry":
            key = "telemetry_raw" if json.get("raw") == "true" else "telemetry"
        else:
            key = action  # action name matches our fixture key for the rest
        return FakeResponse(sample_raw[key])

    monkeypatch.setattr(rpc_module.requests, "post", fake_post)

    metrics = Metrics(CollectorRegistry())
    raw = NanoRpcClient("host", "7076").gather(metrics.latency)

    assert set(raw) == set(COMMANDS)
    assert raw["block_count"]["count"] == "180000000"
    assert raw["stats_counters"]["entries"][0]["type"] == "traffic_tcp"
    assert raw["telemetry_raw"]["metrics"][0]["address"] == "::ffff:1.2.3.4"

    # every command was timed into the nano_rpc_response histogram
    get_count = metrics.registry.get_sample_value
    assert get_count("nano_rpc_response_count", {"method": "version"}) == 1.0
    assert get_count("nano_rpc_response_count", {"method": "telemetry_raw"}) == 1.0
