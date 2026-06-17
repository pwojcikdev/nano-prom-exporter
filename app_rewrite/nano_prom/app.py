"""Application wiring and the main collection loop."""

from __future__ import annotations

import logging
import os
import time

from . import process_stats
from .cli import parse_args
from .config import Settings, load_settings
from .metrics import Metrics
from .rpc import NanoRpcClient
from .stats import parse_stats

log = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=os.environ.get("LOGLEVEL", "INFO").upper(),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # These libraries are noisy at INFO; we only care about our own logs.
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def tick(settings: Settings, metrics: Metrics, rpc: NanoRpcClient) -> None:
    """Run one collect-and-push cycle."""
    raw = rpc.gather(metrics.latency)
    metrics.update_node(parse_stats(raw))

    # Process/system stats are best-effort: a missing nano_node process or an
    # unsupported platform must not stop the RPC metrics from being pushed.
    try:
        metrics.update_process(process_stats.collect_process_snapshot())
        disk = process_stats.collect_disk_usage(settings.node_data_path)
        if disk is not None:
            metrics.update_disk(disk)
    except Exception as e:
        log.debug("process stats failed", exc_info=True)
        log.warning("Failed to gather process stats: %r", e)

    metrics.push(settings)


def run(settings: Settings, metrics: Metrics, rpc: NanoRpcClient) -> None:
    """Loop forever, surviving any single-cycle failure."""
    while True:
        try:
            tick(settings, metrics, rpc)
        except Exception as e:
            log.error("Error: %r", e)
            log.debug("tick failed", exc_info=True)
        time.sleep(settings.interval)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging()
    settings = load_settings(args)

    metrics = Metrics()
    rpc = NanoRpcClient(settings.rpc_host, settings.rpc_port)

    gateways = ", ".join(g.url for g in settings.push_gateways)
    log.info(
        "Started, runid: %s | hostname: %s | interval: %s | push_gateway: %s | rpc: %s:%s",
        settings.runid,
        settings.hostname,
        settings.interval,
        gateways,
        settings.rpc_host,
        settings.rpc_port,
    )
    run(settings, metrics, rpc)
