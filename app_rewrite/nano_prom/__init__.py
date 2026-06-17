"""Prometheus exporter for a Nano node.

Polls a nano_node RPC endpoint plus local process/system stats and pushes the
result to one or more Prometheus Pushgateways on a fixed interval.
"""

__version__ = "0.2.0"
