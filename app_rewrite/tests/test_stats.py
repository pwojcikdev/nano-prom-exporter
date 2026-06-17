from nano_prom.stats import parse_stats, to_multiplier, walk_stats_objects


def test_to_multiplier_known_value():
    # (2^64 - base) / (2^64 - difficulty); base=2^63, difficulty=3*2^62 -> 2.0
    assert to_multiplier(0xC000000000000000, 0x8000000000000000) == 2.0


def test_parse_basic_fields(sample_raw):
    stats = parse_stats(sample_raw)
    assert stats.active_difficulty == "1.0"
    assert stats.network_receive_current == 2.0
    assert stats.block_count["count"] == "180000000"
    assert stats.peer_count == 2
    assert stats.uptime == "123456"
    assert stats.frontiers == "30000000"
    assert stats.online_stake == "130000000000000000000000000000000000000"


def test_telemetry_includes_network_average(sample_raw):
    stats = parse_stats(sample_raw)
    endpoints = [t.endpoint for t in stats.telemetry]
    assert endpoints == ["::ffff:1.2.3.4:7075", "avg_telemetry"]
    avg = stats.telemetry[-1]
    assert avg.block_count == "179999850"
    assert avg.peer_count == "201"


def test_telemetry_when_no_raw_peers(sample_raw):
    sample_raw["telemetry_raw"]["metrics"] = []
    stats = parse_stats(sample_raw)
    assert [t.endpoint for t in stats.telemetry] == ["avg_telemetry"]


def test_walk_stats_objects_nested(sample_raw):
    leaves = set(walk_stats_objects(sample_raw["stats_objects"]["node"]))
    assert ("vote_processor", "votes", "1", "2") in leaves
    assert ("active", "roots", "3", "4") in leaves
    assert ("active", "election_winner_details", "5", "6") in leaves
    # deeper nesting collapses the parent path into the first label
    assert ("deep : a", "b", "7", "8") in leaves


def test_walk_stats_objects_deep_nesting():
    # 4+ levels: the full parent path is joined with " : " and the leaf key is
    # the second label, regardless of depth.
    objects = {
        "l1": {"l2": {"l3": {"leaf": {"count": "9", "size": "10"}}}},
        "w": {"x": {"y": {"z": {"count": "1", "size": "2"}}}},
    }
    leaves = set(walk_stats_objects(objects))
    assert ("l1 : l2 : l3", "leaf", "9", "10") in leaves
    assert ("w : x : y", "z", "1", "2") in leaves
