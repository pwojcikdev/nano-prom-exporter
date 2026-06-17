"""Runtime configuration.

Settings come from command-line arguments and, optionally, an INI file. The INI
file is the only way to configure more than one push gateway or HTTP basic-auth
credentials; when given, its values take precedence over the CLI defaults.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PushGateway:
    """A single Prometheus Pushgateway target."""

    url: str
    username: str = ""
    password: str = ""

    @property
    def requires_auth(self) -> bool:
        return self.username != ""


@dataclass
class Settings:
    rpc_host: str
    rpc_port: str
    node_data_path: Path
    hostname: str
    interval: int
    runid: str
    push_gateways: list[PushGateway] = field(default_factory=list)


def load_settings(args) -> Settings:
    """Build :class:`Settings` from parsed CLI ``args``.

    If ``args.config_path`` is set, the INI file overrides the CLI values and
    defines the push gateways; otherwise a single gateway is built from the
    ``--push_gateway`` / ``--username`` / ``--password`` flags.
    """
    runid = args.runid
    if args.runid_prefix:
        runid = f"{args.runid_prefix}_{runid}"

    settings = Settings(
        rpc_host=args.host,
        rpc_port=args.port,
        node_data_path=Path(args.datapath).expanduser(),
        hostname=args.hostname,
        interval=int(args.interval),
        runid=runid,
        push_gateways=[PushGateway(args.push_gateway, args.username, args.password)],
    )

    if args.config_path:
        _apply_config_file(settings, args.config_path)

    return settings


def _apply_config_file(settings: Settings, config_path: str) -> None:
    config = configparser.ConfigParser()
    config.read(config_path)

    settings.rpc_host = config.get("DEFAULT", "rpcIp", fallback=settings.rpc_host)
    settings.rpc_port = config.get("DEFAULT", "rpcPort", fallback=settings.rpc_port)
    settings.hostname = config.get("DEFAULT", "hostname", fallback=settings.hostname)
    settings.interval = int(
        config.get("DEFAULT", "interval", fallback=settings.interval)
    )
    data_path = config.get("DEFAULT", "nodeDataPath", fallback=None)
    if data_path is not None:
        settings.node_data_path = Path(data_path).expanduser()

    # Every non-DEFAULT section is a push gateway keyed by its URL. If the file
    # defines no gateway sections, keep the gateway from the CLI flags so the
    # exporter still has somewhere to push.
    gateways = []
    for url in config.sections():
        username = config.get(url, "username", fallback="")
        password = config.get(url, "password", fallback="")
        if username and not password:
            raise ValueError(f"Password required for basic auth on gateway: {url}")
        gateways.append(PushGateway(url, username, password))

    if gateways:
        settings.push_gateways = gateways
