"""Parse raw nano_node RPC responses into typed values.

This module is pure data transformation: it takes the dict returned by the RPC
client and produces structures the metrics layer can consume. No network or
Prometheus concerns live here.
"""

from __future__ import annotations

from dataclasses import dataclass


def to_multiplier(difficulty: int, base_difficulty: int) -> float:
    """Convert a raw difficulty value into a multiplier relative to a base."""
    return float((1 << 64) - base_difficulty) / float((1 << 64) - difficulty)


@dataclass
class Telemetry:
    """A single telemetry sample, either from a peer or the network average."""

    endpoint: str
    block_count: str
    cemented_count: str
    unchecked_count: str
    account_count: str
    bandwidth_cap: str
    peer_count: str
    protocol_version: str
    major_version: str
    minor_version: str
    patch_version: str
    pre_release_version: str
    uptime: str
    maker: str
    timestamp: str

    @classmethod
    def from_metric(cls, metric: dict) -> "Telemetry":
        # Per-peer telemetry carries an address/port; the averaged telemetry
        # sample does not, so we label it "avg_telemetry".
        if "address" in metric:
            endpoint = f"{metric['address']}:{metric['port']}"
        else:
            endpoint = "avg_telemetry"
        return cls(
            endpoint=endpoint,
            block_count=metric["block_count"],
            cemented_count=metric["cemented_count"],
            unchecked_count=metric["unchecked_count"],
            account_count=metric["account_count"],
            bandwidth_cap=metric["bandwidth_cap"],
            peer_count=metric["peer_count"],
            protocol_version=metric["protocol_version"],
            major_version=metric["major_version"],
            minor_version=metric["minor_version"],
            patch_version=metric["patch_version"],
            pre_release_version=metric["pre_release_version"],
            uptime=metric["uptime"],
            maker=str(metric["maker"]),
            timestamp=metric["timestamp"],
        )


@dataclass
class NodeStats:
    """RPC-derived node statistics, ready to be turned into metrics."""

    active_difficulty: str
    network_receive_current: float
    block_count: dict
    peer_count: int
    stats_counters: list[dict]
    stats_objects: dict
    uptime: str
    version: dict
    frontiers: str
    online_stake: str
    quorum_delta: str
    peers_stake: str
    trended_stake: str
    telemetry: list[Telemetry]


def parse_stats(raw: dict) -> NodeStats:
    """Turn the raw ``{command: response}`` dict into a :class:`NodeStats`."""
    difficulty = raw["active_difficulty"]
    quorum = raw["confirmation_quorum"]

    # Per-peer telemetry plus the network-average sample, all labelled by endpoint.
    raw_telemetry = raw["telemetry_raw"]["metrics"] or []
    telemetry = [Telemetry.from_metric(m) for m in raw_telemetry]
    telemetry.append(Telemetry.from_metric(raw["telemetry"]))

    return NodeStats(
        active_difficulty=difficulty["multiplier"],
        network_receive_current=to_multiplier(
            int(difficulty["network_receive_current"], 16),
            int(difficulty["network_receive_minimum"], 16),
        ),
        block_count=raw["block_count"],
        peer_count=len(raw["peers"]["peers"]),
        stats_counters=raw["stats_counters"]["entries"],
        stats_objects=raw["stats_objects"]["node"],
        uptime=raw["uptime"]["seconds"],
        version=raw["version"],
        frontiers=raw["frontier_count"]["count"],
        online_stake=quorum["online_stake_total"],
        quorum_delta=quorum["quorum_delta"],
        peers_stake=quorum["peers_stake_total"],
        trended_stake=quorum["trended_stake_total"],
        telemetry=telemetry,
    )


def walk_stats_objects(objects: dict):
    """Yield ``(group, name, count, size)`` for every leaf in the nested
    ``stats objects`` tree.

    A leaf is any dict containing a ``size`` key. ``group`` is the parent path
    joined with " : " (matching the legacy label format), ``name`` is the leaf's
    key.
    """
    yield from _walk(objects, [])


def _walk(node: dict, path: list[str]):
    for key, value in node.items():
        if not isinstance(value, dict):
            continue
        if "size" in value:
            yield " : ".join(path), key, value["count"], value["size"]
        else:
            yield from _walk(value, path + [key])
