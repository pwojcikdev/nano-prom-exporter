# nano-prom-exporter

A small daemon that collects [Nano](https://nano.org) node statistics and pushes
them to a Prometheus [Pushgateway](https://github.com/prometheus/pushgateway).

This is a clean reimplementation of the original `nano_prom_exporter`. It
exposes the same metric names and labels, so existing Prometheus/Grafana setups
keep working unchanged.

## What it does

On a fixed interval the exporter:

1. Calls the node's RPC endpoint for version, block count, peers, stats
   (counters and objects), uptime, active difficulty, frontier count,
   confirmation quorum, and telemetry (per-peer and network average). Each call
   is timed into the `nano_rpc_response` histogram.
2. Collects local system stats with `psutil`: network bytes in/out, `nano_node`
   CPU usage, per-thread CPU (Linux only), database file size, and disk volume
   usage.
3. Translates everything into Prometheus gauges and pushes them to the
   configured gateway(s).

The loop never exits on error: a failed cycle is logged and retried on the next
interval.

## Install

```bash
cd app_rewrite
python3 -m venv .venv && . .venv/bin/activate
pip install -e .            # add ".[dev]" to also install pytest
```

## Run

```bash
nano-prom --host localhost --port 7076 --push_gateway http://localhost:9091
# or, equivalently, without installing the console script:
python -m nano_prom --host localhost --port 7076
```

### Command-line options

| Flag | Default | Description |
| --- | --- | --- |
| `--host` | `localhost` | RPC host |
| `--port` | `7076` | RPC port |
| `--datapath` | `~/Nano` | Node data directory (for DB/volume metrics) |
| `--push_gateway` | `http://localhost:9091` | Pushgateway URL |
| `--hostname` | system hostname | Instance name reported to Prometheus |
| `--interval` | `3` | Seconds between pushes |
| `--username` / `--password` | empty | HTTP basic auth for the gateway |
| `--config_path` | none | Path to a config.ini (see below) |
| `--runid` | timestamp | Job name reported to Prometheus |
| `--runid_prefix` | none | Optional prefix prepended to `--runid` |

## Configure

For a single gateway the CLI flags are enough. To push to **multiple** gateways
or use **basic auth**, pass `--config_path` pointing at an INI file. See
[`config.example.ini`](config.example.ini); its `[DEFAULT]` values override the
CLI flags and each other section is a gateway keyed by its URL.

Two optional environment variables (see [`.env.example`](.env.example)):

- `LOGLEVEL` — logging verbosity (default `INFO`).
- `NANO_PROM_DEBUG` — if set, logs each stats object during collection.

No secrets are baked into the code; credentials come only from CLI flags or the
config file you supply.

## Test

```bash
pip install -e ".[dev]"
pytest
```

The tests are self-contained — they use a captured RPC response fixture and a
fake HTTP layer, so no running node or gateway is required. They cover RPC
response parsing, the produced metric names/labels/values, config loading
(including multi-gateway INI files), and a smoke test of one full collection
cycle.

## Project layout

```
nano_prom/
  cli.py            argparse front-end
  config.py         Settings + config.ini loading
  rpc.py            nano_node RPC client
  stats.py          parse RPC responses into typed values
  process_stats.py  psutil process / network / disk collection
  metrics.py        Prometheus metric definitions + push
  app.py            wiring and the main loop
tests/
```

## Notes and assumptions

- **Per-thread CPU is Linux-only.** Thread names come from `/proc`, which other
  platforms don't expose; thread metrics are simply skipped elsewhere. All other
  metrics work cross-platform.
- **DB and volume metrics require a real data directory.** They are emitted only
  when `<datapath>/data.ldb` exists; otherwise they are skipped.
- **`confirmation_history` is intentionally not collected** — it is a slow RPC
  call on the node.
- Sample RPC values in the test fixture are representative, not captured from a
  specific node version; field *shapes* match the RPC API the code consumes.
