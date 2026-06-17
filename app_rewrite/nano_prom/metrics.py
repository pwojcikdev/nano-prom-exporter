"""Prometheus metric definitions and push logic.

`Metrics` owns the registry and every series this exporter produces. The
``update_*`` methods translate parsed data into metric values; ``push`` ships
the registry to the configured gateways.
"""

from __future__ import annotations

import logging
import os

from prometheus_client import CollectorRegistry, Gauge, Histogram, Info, push_to_gateway
from prometheus_client.exposition import basic_auth_handler

from .config import Settings
from .process_stats import DiskUsage, ProcessSnapshot
from .stats import NodeStats, Telemetry, walk_stats_objects

log = logging.getLogger(__name__)


class Metrics:
    def __init__(self, registry: CollectorRegistry | None = None):
        self.registry = registry or CollectorRegistry()
        reg = self.registry

        # RPC call timing.
        self.latency = Histogram(
            "nano_rpc_response",
            "response time from rpc calls",
            ["method"],
            registry=reg,
        )

        # Node stats from RPC.
        self.active_difficulty = Gauge(
            "nano_active_difficulty", "Active Difficulty Multiplier", registry=reg
        )
        self.network_receive_current = Gauge(
            "nano_active_difficulty_receive", "current receive multiplier", registry=reg
        )
        self.block_count = Gauge(
            "nano_block_count", "Block Count Statistics", ["type"], registry=reg
        )
        self.peer_count = Gauge("nano_node_peer_count", "Peer Count", registry=reg)
        self.stats_counters = Gauge(
            "nano_stats_counters",
            "Stats Counters",
            ["type", "detail", "dir"],
            registry=reg,
        )
        self.stats_objects_count = Gauge(
            "nano_stats_objects_count",
            "Objects from nano_stats by count",
            ["l1", "l2"],
            registry=reg,
        )
        self.stats_objects_size = Gauge(
            "nano_stats_objects_size",
            "Objects from nano_stats by size",
            ["l1", "l2"],
            registry=reg,
        )
        self.uptime = Gauge("nano_uptime", "Uptime Counter in seconds", registry=reg)
        self.version = Info("nano_version", "Nano Version details", registry=reg)
        self.frontiers = Gauge(
            "nano_node_frontier_count", "local node frontier count", registry=reg
        )
        self.quorum_delta = Gauge(
            "nano_node_quorum_delta",
            "Quorum Delta from Confirmation Quorum RPC",
            registry=reg,
        )
        self.online_stake = Gauge(
            "nano_node_online_stake_total", "Online Stake Total", registry=reg
        )
        self.peers_stake = Gauge(
            "nano_node_peers_stake_total", "Peers Stake Total", registry=reg
        )
        self.trended_stake = Gauge(
            "nano_node_trended_stake_total", "Trended Stake Total", registry=reg
        )

        # Local process / system stats.
        self.cpu = Gauge(
            "nano_node_cpu_usage", "nano_node cpu usage", ["pid"], registry=reg
        )
        self.threads = Gauge(
            "nano_node_threads", "Thread %", ["pid", "tid", "name"], registry=reg
        )
        self.network_tx = Gauge("network_raw_tx", "Raw tx from psutil", registry=reg)
        self.network_rx = Gauge("network_raw_rx", "Raw rx from psutil", registry=reg)
        self.database_size = Gauge(
            "nano_node_database", "nano_node data", ["type"], registry=reg
        )
        self.volume_free = Gauge(
            "nano_node_volume_free", "data volume stats", registry=reg
        )
        self.volume_used = Gauge(
            "nano_node_volume_used", "data volume stats", registry=reg
        )
        self.volume_total = Gauge(
            "nano_node_volume_total", "data volume stats", registry=reg
        )

        # Telemetry, labelled per endpoint.
        self.telemetry_blocks = self._telemetry_gauge(
            "telemetry_raw_blocks", "block count"
        )
        self.telemetry_cemented = self._telemetry_gauge(
            "telemetry_raw_cemented", "cemented count"
        )
        self.telemetry_unchecked = self._telemetry_gauge(
            "telemetry_raw_unchecked", "unchecked count"
        )
        self.telemetry_accounts = self._telemetry_gauge(
            "telemetry_raw_accounts", "accounts count"
        )
        self.telemetry_bandwidth = self._telemetry_gauge(
            "telemetry_raw_bandwidth", "bandwidth cap"
        )
        self.telemetry_peers = self._telemetry_gauge("telemetry_raw_peer", "peer count")
        self.telemetry_protocol = self._telemetry_gauge(
            "telemetry_raw_protocol", "protocol version"
        )
        self.telemetry_major = self._telemetry_gauge(
            "telemetry_raw_major", "major version"
        )
        self.telemetry_minor = self._telemetry_gauge(
            "telemetry_raw_minor", "minor version"
        )
        self.telemetry_patch = self._telemetry_gauge(
            "telemetry_raw_patch", "patch version"
        )
        self.telemetry_pre = self._telemetry_gauge(
            "telemetry_raw_pre", "pre-release version"
        )
        self.telemetry_uptime = self._telemetry_gauge(
            "telemetry_raw_uptime", "uptime counter"
        )
        self.telemetry_timestamp = self._telemetry_gauge(
            "telemetry_raw_timestamp", "updated timestamp"
        )
        self.telemetry_maker = Gauge(
            "telemetry_raw_maker",
            "Raw Telemetry maker by endpoint",
            ["endpoint", "maker"],
            registry=reg,
        )

    def _telemetry_gauge(self, name: str, what: str) -> Gauge:
        return Gauge(
            name,
            f"Raw Telemetry {what} by endpoint",
            ["endpoint"],
            registry=self.registry,
        )

    def update_node(self, stats: NodeStats) -> None:
        self.active_difficulty.set(stats.active_difficulty)
        self.network_receive_current.set(stats.network_receive_current)
        self.uptime.set(stats.uptime)
        self.frontiers.set(stats.frontiers)
        self.quorum_delta.set(stats.quorum_delta)
        self.online_stake.set(stats.online_stake)
        self.peers_stake.set(stats.peers_stake)
        self.trended_stake.set(stats.trended_stake)
        self.peer_count.set(stats.peer_count)

        for block_type, value in stats.block_count.items():
            self.block_count.labels(block_type).set(value)

        for entry in stats.stats_counters:
            self.stats_counters.labels(
                entry["type"], entry["detail"], entry["dir"]
            ).set(entry["value"])

        self.version.info({key: stats.version[key] for key in _VERSION_FIELDS})

        debug = bool(os.getenv("NANO_PROM_DEBUG"))
        for group, name, count, size in walk_stats_objects(stats.stats_objects):
            self.stats_objects_size.labels(group, name).set(size)
            self.stats_objects_count.labels(group, name).set(count)
            if debug:
                log.debug(
                    "stats_objects %s / %s count=%s size=%s", group, name, count, size
                )

        for telemetry in stats.telemetry:
            self._update_telemetry(telemetry)

    def _update_telemetry(self, t: Telemetry) -> None:
        self.telemetry_blocks.labels(t.endpoint).set(t.block_count)
        self.telemetry_cemented.labels(t.endpoint).set(t.cemented_count)
        self.telemetry_unchecked.labels(t.endpoint).set(t.unchecked_count)
        self.telemetry_accounts.labels(t.endpoint).set(t.account_count)
        self.telemetry_bandwidth.labels(t.endpoint).set(t.bandwidth_cap)
        self.telemetry_peers.labels(t.endpoint).set(t.peer_count)
        self.telemetry_protocol.labels(t.endpoint).set(t.protocol_version)
        self.telemetry_major.labels(t.endpoint).set(t.major_version)
        self.telemetry_minor.labels(t.endpoint).set(t.minor_version)
        self.telemetry_patch.labels(t.endpoint).set(t.patch_version)
        self.telemetry_pre.labels(t.endpoint).set(t.pre_release_version)
        self.telemetry_uptime.labels(t.endpoint).set(t.uptime)
        self.telemetry_timestamp.labels(t.endpoint).set(t.timestamp)
        self.telemetry_maker.labels(t.endpoint, t.maker).set(1)

    def update_process(self, snapshot: ProcessSnapshot) -> None:
        self.network_tx.set(snapshot.tx)
        self.network_rx.set(snapshot.rx)
        for pid, percent in snapshot.cpu:
            self.cpu.labels(pid).set(percent)
        for thread in snapshot.threads:
            self.threads.labels(thread.pid, thread.tid, thread.name).set(thread.percent)

    def update_disk(self, disk: DiskUsage) -> None:
        self.database_size.labels("lmdb").set(disk.db_size)
        self.volume_total.set(disk.total)
        self.volume_used.set(disk.used)
        self.volume_free.set(disk.free)

    def push(self, settings: Settings) -> None:
        for gateway in settings.push_gateways:
            if gateway.requires_auth:
                push_to_gateway(
                    gateway.url,
                    job=settings.hostname,
                    registry=self.registry,
                    handler=_auth_handler(gateway.username, gateway.password),
                )
            else:
                push_to_gateway(
                    gateway.url,
                    job=settings.runid,
                    grouping_key={"instance": settings.hostname},
                    registry=self.registry,
                )


_VERSION_FIELDS = (
    "rpc_version",
    "store_version",
    "protocol_version",
    "node_vendor",
    "store_vendor",
    "network",
    "network_identifier",
    "build_info",
)


def _auth_handler(username: str, password: str):
    def handle(url, method, timeout, headers, data):
        return basic_auth_handler(
            url, method, timeout, headers, data, username, password
        )

    return handle
