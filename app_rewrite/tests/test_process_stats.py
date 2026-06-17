from prometheus_client import CollectorRegistry

from nano_prom.metrics import Metrics
from nano_prom.process_stats import (
    DiskUsage,
    ProcessSnapshot,
    ThreadCpu,
    collect_disk_usage,
    network_io,
)


def test_network_io_returns_ints():
    tx, rx = network_io()
    assert isinstance(tx, int) and isinstance(rx, int)


def test_collect_disk_usage_absent(tmp_path):
    assert collect_disk_usage(tmp_path) is None


def test_collect_disk_usage_present(tmp_path):
    (tmp_path / "data.ldb").write_bytes(b"x" * 10)
    usage = collect_disk_usage(tmp_path)
    assert usage is not None
    assert usage.db_size == 10
    assert usage.total > 0


def test_update_process_sets_gauges():
    m = Metrics(CollectorRegistry())
    m.update_process(
        ProcessSnapshot(
            tx=100, rx=200, cpu=[(42, 12.5)], threads=[ThreadCpu(42, 7, "worker", 3.0)]
        )
    )
    assert m.registry.get_sample_value("network_raw_tx") == 100.0
    assert m.registry.get_sample_value("network_raw_rx") == 200.0
    assert m.registry.get_sample_value("nano_node_cpu_usage", {"pid": "42"}) == 12.5
    assert (
        m.registry.get_sample_value(
            "nano_node_threads", {"pid": "42", "tid": "7", "name": "worker"}
        )
        == 3.0
    )


def test_update_disk_sets_gauges():
    m = Metrics(CollectorRegistry())
    m.update_disk(DiskUsage(db_size=10, total=1000, used=400, free=600))
    assert m.registry.get_sample_value("nano_node_database", {"type": "lmdb"}) == 10.0
    assert m.registry.get_sample_value("nano_node_volume_free") == 600.0
    assert m.registry.get_sample_value("nano_node_volume_total") == 1000.0
