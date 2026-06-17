from prometheus_client import CollectorRegistry

from nano_prom.metrics import Metrics
from nano_prom.stats import parse_stats


def build(sample_raw):
    metrics = Metrics(CollectorRegistry())
    metrics.update_node(parse_stats(sample_raw))
    return metrics


def get(metrics, name, labels=None):
    return metrics.registry.get_sample_value(name, labels or {})


def test_scalar_metrics(sample_raw):
    m = build(sample_raw)
    assert get(m, "nano_uptime") == 123456.0
    assert get(m, "nano_node_frontier_count") == 30000000.0
    assert get(m, "nano_node_peer_count") == 2.0
    assert get(m, "nano_active_difficulty") == 1.0
    assert get(m, "nano_active_difficulty_receive") == 2.0
    assert get(m, "nano_node_online_stake_total") == float(
        sample_raw["confirmation_quorum"]["online_stake_total"]
    )


def test_block_count_and_counters(sample_raw):
    m = build(sample_raw)
    assert get(m, "nano_block_count", {"type": "count"}) == 180000000.0
    assert get(m, "nano_block_count", {"type": "cemented"}) == 179999990.0
    assert (
        get(
            m,
            "nano_stats_counters",
            {"type": "traffic_tcp", "detail": "all", "dir": "in"},
        )
        == 123.0
    )


def test_stats_objects(sample_raw):
    m = build(sample_raw)
    assert (
        get(m, "nano_stats_objects_size", {"l1": "vote_processor", "l2": "votes"})
        == 2.0
    )
    assert (
        get(m, "nano_stats_objects_count", {"l1": "vote_processor", "l2": "votes"})
        == 1.0
    )
    assert get(m, "nano_stats_objects_size", {"l1": "deep : a", "l2": "b"}) == 8.0
    assert get(m, "nano_stats_objects_count", {"l1": "deep : a", "l2": "b"}) == 7.0


def test_telemetry_per_endpoint_and_average(sample_raw):
    m = build(sample_raw)
    peer = {"endpoint": "::ffff:1.2.3.4:7075"}
    avg = {"endpoint": "avg_telemetry"}
    assert get(m, "telemetry_raw_blocks", peer) == 179999900.0
    assert get(m, "telemetry_raw_blocks", avg) == 179999850.0
    assert get(m, "telemetry_raw_peer", avg) == 201.0
    assert (
        get(m, "telemetry_raw_maker", {"endpoint": "avg_telemetry", "maker": "0"})
        == 1.0
    )


def test_version_info(sample_raw):
    m = build(sample_raw)
    labels = {
        "rpc_version": "1",
        "store_version": "21",
        "protocol_version": "19",
        "node_vendor": "Nano V25.1",
        "store_vendor": "LMDB 0.9.29",
        "network": "live",
        "network_identifier": sample_raw["version"]["network_identifier"],
        "build_info": "abc123",
    }
    assert get(m, "nano_version_info", labels) == 1.0
