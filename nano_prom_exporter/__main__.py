"""Nano Prometheus Export to Gateway

This Script allows the user to export specific
nano_node based stats to a prometheus gateway
limiting the amount of attack surface normally
needed for exposing stats like this

This script requires
`promethues_client`
`psutil`
`requests` be installed
"""

import argparse
import logging
import os
import time
from datetime import datetime
from socket import gethostname

from prometheus_client import CollectorRegistry, Histogram

from .config import Config
from .nanoRPC import nanoRPC
from .nanoStats import nano_nodeProcess, nanoProm
from .repeatedTimer import RepeatedTimer

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", level=os.environ.get("LOGLEVEL", "INFO").upper(), datefmt="%Y-%m-%d %H:%M:%S")
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def generate_runid():
    runid = str(datetime.now()).replace(" ", "_")
    return runid


parser = argparse.ArgumentParser(prog="nano_prom", description="configuration values")
parser.add_argument("--host", help='"localhost" default\thost string', default="localhost", action="store")
parser.add_argument("--port", help='"7076" default\trpc port', default="7076", action="store")
parser.add_argument("--datapath", help='"~\\Nano" as default', default="~\\Nano\\", action="store")
parser.add_argument(
    "--push_gateway",
    help='"http://localhost:9091" prometheus push gateway',
    default="http://localhost:9091",
    action="store",
)
parser.add_argument("--hostname", help="instance name to pass to prometheus", default=gethostname(), action="store")
parser.add_argument("--interval", help="interval to sleep", default="3", action="store", type=int)
parser.add_argument("--username", help="Username for basic auth on push_gateway", default="", action="store")
parser.add_argument("--password", help="Password for basic auth on push_gateway", default="", action="store")
parser.add_argument("--config_path", help="Path to config.ini \nIgnores other CLI arguments", default=None, action="store")
parser.add_argument("--runid", help="job name to pass to prometheus", default=generate_runid(), action="store")
parser.add_argument("--runid_prefix", help="job name to pass to prometheus", default=None, action="store")

args = parser.parse_args()
cnf = Config(args)
registry = CollectorRegistry()
rpcLatency = Histogram("nano_rpc_response", "response time from rpc calls", ["method"], registry=registry)

statsCollection = nanoRPC(cnf)
promCollection = nanoProm(cnf, registry)
process_stats = nano_nodeProcess(promCollection)

last_time = 0


def try_gather_process_stats():
    try:
        process_stats.node_process_stats()
    except Exception as e:
        logging.debug(e, exc_info=True)
        logging.warning(f"Failed to gather process stats: {repr(e)}")


def main_impl():
    logging.debug("Starting main loop")

    stats = statsCollection.gatherStats(rpcLatency)

    try_gather_process_stats()

    promCollection.update(stats)
    promCollection.pushStats(registry)

    global last_time
    curr_time = time.time()
    logging.debug("Finished main loop, elapsed time: %s", curr_time - last_time)
    last_time = curr_time


def main():
    logging.info(
        f"Started, runid: {args.runid} | hostname: {args.hostname} | interval: {args.interval} | push_gateway: {args.push_gateway} | rpc: {args.host}:{args.port}"
    )

    while True:
        try:
            main_impl()
        except Exception as e:
            logging.error(f"Error: {repr(e)}")
            logging.debug(e, exc_info=True)

        logging.debug("Sleeping for: %s", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
