import textwrap

import pytest

from nano_prom.cli import parse_args
from nano_prom.config import load_settings


def test_defaults_single_gateway():
    settings = load_settings(parse_args([]))
    assert len(settings.push_gateways) == 1
    gateway = settings.push_gateways[0]
    assert gateway.url == "http://localhost:9091"
    assert gateway.requires_auth is False
    assert settings.interval == 3
    assert isinstance(settings.interval, int)
    assert str(settings.node_data_path).endswith("Nano")


def test_runid_prefix_applied():
    settings = load_settings(parse_args(["--runid", "abc", "--runid_prefix", "pre"]))
    assert settings.runid == "pre_abc"


def test_config_file_overrides_and_multiple_gateways(tmp_path):
    ini = tmp_path / "config.ini"
    ini.write_text(
        textwrap.dedent(
            """
            [DEFAULT]
            rpcIp = node.local
            rpcPort = 17076
            interval = 10
            nodeDataPath = /var/nano

            [http://gw1:9091]

            [http://gw2:9092]
            username = u
            password = p
            """
        )
    )
    settings = load_settings(parse_args(["--config_path", str(ini)]))
    assert settings.rpc_host == "node.local"
    assert settings.rpc_port == "17076"
    assert settings.interval == 10
    assert str(settings.node_data_path) == "/var/nano"

    by_url = {g.url: g for g in settings.push_gateways}
    assert set(by_url) == {"http://gw1:9091", "http://gw2:9092"}
    assert by_url["http://gw1:9091"].requires_auth is False
    assert by_url["http://gw2:9092"].requires_auth is True
    assert by_url["http://gw2:9092"].password == "p"


def test_basic_auth_username_without_password_raises(tmp_path):
    ini = tmp_path / "bad.ini"
    ini.write_text("[http://gw:9091]\nusername = u\n")
    with pytest.raises(ValueError):
        load_settings(parse_args(["--config_path", str(ini)]))


def test_config_without_gateway_sections_keeps_cli_gateway(tmp_path):
    # A config file that only overrides [DEFAULT] values must not leave the
    # exporter with nowhere to push; the CLI gateway is retained.
    ini = tmp_path / "default_only.ini"
    ini.write_text("[DEFAULT]\nrpcPort = 17076\n")
    settings = load_settings(
        parse_args(["--config_path", str(ini), "--push_gateway", "http://cli:9091"])
    )
    assert settings.rpc_port == "17076"
    assert [g.url for g in settings.push_gateways] == ["http://cli:9091"]
