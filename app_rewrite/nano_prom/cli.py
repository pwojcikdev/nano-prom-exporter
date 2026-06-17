"""Command-line argument parsing."""

from __future__ import annotations

import argparse
from datetime import datetime
from socket import gethostname


def generate_runid() -> str:
    """A timestamp-based default job name, e.g. ``2026-05-28_12:00:00``."""
    return str(datetime.now()).replace(" ", "_")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nano-prom", description="Export nano_node stats to Prometheus"
    )
    parser.add_argument(
        "--host", default="localhost", help="RPC host (default: localhost)"
    )
    parser.add_argument("--port", default="7076", help="RPC port (default: 7076)")
    parser.add_argument(
        "--datapath",
        default="~/Nano",
        help="Path to the Nano data directory (default: ~/Nano)",
    )
    parser.add_argument(
        "--push_gateway",
        default="http://localhost:9091",
        help="Prometheus push gateway URL (default: http://localhost:9091)",
    )
    parser.add_argument(
        "--hostname",
        default=gethostname(),
        help="Instance name reported to Prometheus (default: system hostname)",
    )
    parser.add_argument(
        "--interval", type=int, default=3, help="Seconds between pushes (default: 3)"
    )
    parser.add_argument(
        "--username", default="", help="Basic-auth username for the push gateway"
    )
    parser.add_argument(
        "--password", default="", help="Basic-auth password for the push gateway"
    )
    parser.add_argument(
        "--config_path",
        default=None,
        help="Path to config.ini (enables multiple gateways and basic auth)",
    )
    parser.add_argument(
        "--runid",
        default=None,
        help="Job name reported to Prometheus (default: timestamp)",
    )
    parser.add_argument(
        "--runid_prefix", default=None, help="Optional prefix for --runid"
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args = build_parser().parse_args(argv)
    if args.runid is None:
        args.runid = generate_runid()
    return args
