from prometheus_client import CollectorRegistry

import nano_prom.metrics as metrics_module
import nano_prom.process_stats as process_stats_module
from nano_prom.app import tick
from nano_prom.cli import parse_args
from nano_prom.config import load_settings
from nano_prom.metrics import Metrics
from nano_prom.process_stats import ProcessSnapshot


class StubRpc:
    """Stands in for NanoRpcClient: returns canned data, no network."""

    def __init__(self, raw):
        self._raw = raw

    def gather(self, latency):
        with latency.labels("version").time():  # exercise the histogram
            pass
        return self._raw


def test_cli_defaults():
    args = parse_args([])
    assert args.host == "localhost"
    assert args.port == "7076"
    assert args.interval == 3
    assert args.push_gateway == "http://localhost:9091"
    assert args.runid  # auto-generated timestamp


def test_full_tick_collects_and_pushes(monkeypatch, tmp_path, sample_raw):
    pushed = []
    monkeypatch.setattr(
        metrics_module, "push_to_gateway", lambda *a, **k: pushed.append((a, k))
    )

    settings = load_settings(parse_args(["--datapath", str(tmp_path)]))
    metrics = Metrics(CollectorRegistry())

    tick(settings, metrics, StubRpc(sample_raw))

    assert len(pushed) == 1
    assert metrics.registry.get_sample_value("nano_uptime") == 123456.0
    # the network-average telemetry series must be present after a full cycle
    assert (
        metrics.registry.get_sample_value(
            "telemetry_raw_blocks", {"endpoint": "avg_telemetry"}
        )
        == 179999850.0
    )


def test_tick_wires_process_and_disk_branches(monkeypatch, tmp_path, sample_raw):
    monkeypatch.setattr(metrics_module, "push_to_gateway", lambda *a, **k: None)
    # Deterministic snapshot so we can prove tick() routed it into the metrics.
    monkeypatch.setattr(
        process_stats_module,
        "collect_process_snapshot",
        lambda: ProcessSnapshot(tx=12345, rx=67890),
    )

    settings = load_settings(parse_args(["--datapath", str(tmp_path)]))
    metrics = Metrics(CollectorRegistry())
    tick(settings, metrics, StubRpc(sample_raw))

    # Process branch ran and was wired through (0.0 if the branch were skipped).
    assert metrics.registry.get_sample_value("network_raw_tx") == 12345.0
    assert metrics.registry.get_sample_value("network_raw_rx") == 67890.0
    # No data.ldb under tmp_path -> disk branch skipped, so this series is absent.
    assert (
        metrics.registry.get_sample_value("nano_node_database", {"type": "lmdb"})
        is None
    )
