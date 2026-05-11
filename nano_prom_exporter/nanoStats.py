from collections import namedtuple
import logging
from math import inf
import os

import psutil
from prometheus_client import Gauge, Histogram, Info, push_to_gateway
from prometheus_client.exposition import basic_auth_handler


class telemetry_raw(object):
    def __init__(self, m):
        if "address" in m:
            self.endpoint = str(m["address"]) + ":" + str(m["port"])
            self.node_id = m["node_id"]
        else:
            self.endpoint = "avg_telemetry"
            self.node_id = "avg_telemetry"

        self.block_count = m["block_count"]
        self.cemented_count = m["cemented_count"]
        self.unchecked_count = m["unchecked_count"]
        self.account_count = m["account_count"]
        self.bandwidth_cap = m["bandwidth_cap"]
        self.peer_count = m["peer_count"]
        self.protocol = m["protocol_version"]
        self.major = m["major_version"]
        self.minor = m["minor_version"]
        self.patch = m["patch_version"]
        self.pre_release = m["pre_release_version"]
        self.uptime = m["uptime"]
        self.genesis_block = m["genesis_block"]
        self.maker = m["maker"]
        self.timestamp = m["timestamp"]
        self.active_difficulty = m["active_difficulty"]


class NetworkUsage(object):
    def __init__(self):
        poll = psutil.net_io_counters()
        self.tx = poll.bytes_sent
        self.rx = poll.bytes_recv

mythread = namedtuple('pthread', ['id', 'user_time', 'system_time', 'name'])

def threads(self):
    from psutil import _pslinux as pslinux
    from psutil import _common as pscommon

    thread_ids = os.listdir("%s/%s/task" % (psutil.PROCFS_PATH, self.pid))
    thread_ids.sort()
    retlist = []
    hit_enoent = False
    for thread_id in thread_ids:
        fname = "%s/%s/task/%s/stat" % (
            psutil.PROCFS_PATH, self.pid, thread_id)
        try:
            with pscommon.open_text(fname) as f:
                data = f.read().strip()
        except FileNotFoundError:
            # no such file or directory; it means thread
            # disappeared on us
            hit_enoent = True
            continue
        name = data[data.find('(') + 1:data.rfind(')')]
        values = data[data.find(')') + 2:].split(' ')
        utime = float(values[11]) / pslinux.CLOCK_TICKS
        stime = float(values[12]) / pslinux.CLOCK_TICKS
        ntuple = mythread(int(thread_id), utime, stime, name)
        retlist.append(ntuple)
    if hit_enoent:
        self._assert_alive()
    return retlist


class nano_nodeProcess:
    def __init__(self, nanoProm):
        self.nanoProm = nanoProm

    def find_procs_by_name(self, name):
        """Return a list of processes matching 'name'."""
        ls = []
        for p in psutil.process_iter(attrs=["name", "pid"]):
            if name in p.info["name"]:
                ls.append(p)
        return ls

    def node_process_stats(self):
        poll = NetworkUsage()
        self.nanoProm.network_raw_tx.set(poll.tx)
        self.nanoProm.network_raw_rx.set(poll.rx)
        nano_pid = self.find_procs_by_name("nano_node")
        assert len(nano_pid) > 0
        for a in nano_pid:
            self.get_threads_cpu_percent(a)
            # self.nanoProm.rss.labels(a.pid).set(a.memory_info().rss)
            # self.nanoProm.vms.labels(a.pid).set(a.memory_info().vms)
            # self.nanoProm.pp.labels(a.pid).set(a.memory_info().paged_pool)
            self.nanoProm.cpu.labels(a.pid).set(a.cpu_percent(interval=0.1))

    def get_threads_cpu_percent(self, p, interval=0.1):
        total_percent = p.cpu_percent(interval)
        total_time = sum(p.cpu_times())
        for t in threads(p):
            self.nanoProm.threads.labels(p.pid, t.id, t.name).set(
                total_percent * ((t.system_time + t.user_time) / total_time)
            )


class nanoProm:
    def __init__(self, config, registry):
        self.config = config
        self.ActiveDifficulty = Gauge(
            "nano_active_difficulty", "Active Difficulty Multiplier", registry=registry
        )
        self.NetworkReceiveCurrent = Gauge(
            "nano_active_difficulty_receive",
            "current receive multiplier",
            registry=registry,
        )
        self.threads = Gauge(
            "nano_node_threads", "Thread %", ["pid", "tid", "name"], registry=registry
        )
        self.BlockCount = Gauge(
            "nano_block_count", "Block Count Statistics", ["type"], registry=registry
        )
        # self.ConfirmationHistoryStats = Gauge(
        #     "nano_confirmation_history_stats",
        #     "Block Confirmation Average",
        #     ["type"],
        #     registry=registry,
        # )
        # self.ConfirmationHistoryHist = Histogram(
        #     "nano_confirmation_history_hist",
        #     "Block Confirmation Histogram",
        #     ["type"],
        #     registry=registry,
        #     buckets=[.1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 30.0, 60.0, 120.0, 240.0, 300.0, inf]
        # )
        self.PeersCount = Gauge("nano_node_peer_count", "Peer Cout", registry=registry)
        self.StatsCounters = Gauge(
            "nano_stats_counters",
            "Stats Counters",
            ["type", "detail", "dir"],
            registry=registry,
        )
        self.StatsObjectsCount = Gauge(
            "nano_stats_objects_count",
            "Objects from nano_stats by count",
            ["l1", "l2"],
            registry=registry,
        )
        self.StatsObjectsSize = Gauge(
            "nano_stats_objects_size",
            "Objects from nano_stats by size",
            ["l1", "l2"],
            registry=registry,
        )
        self.Uptime = Gauge(
            "nano_uptime", "Uptime Counter in seconds", registry=registry
        )
        self.Version = Info("nano_version", "Nano Version details", registry=registry)
        self.rss = Gauge(
            "nano_node_memory_rss",
            "nano_node process memory",
            ["pid"],
            registry=registry,
        )
        self.vms = Gauge(
            "nano_node_memory_vms",
            "nano_node process memory",
            ["pid"],
            registry=registry,
        )
        self.pp = Gauge(
            "nano_node_memory_paged_pool",
            "nano_node process memory",
            ["pid"],
            registry=registry,
        )
        self.cpu = Gauge(
            "nano_node_cpu_usage", "nano_node cpu usage", ["pid"], registry=registry
        )
        self.databaseSize = Gauge(
            "nano_node_database", "nano_node data", ["type"], registry=registry
        )
        self.databaseVolumeFree = Gauge(
            "nano_node_volume_free", "data volume stats", registry=registry
        )
        self.databaseVolumeUsed = Gauge(
            "nano_node_volume_used", "data volume stats", registry=registry
        )
        self.databaseVolumeTotal = Gauge(
            "nano_node_volume_total", "data volume stats", registry=registry
        )
        self.Frontiers = Gauge(
            "nano_node_frontier_count", "local node frontier count", registry=registry
        )
        self.QuorumDelta = Gauge(
            "nano_node_quorum_delta",
            "Quorum Delta from Confirmation Quorum RPC",
            registry=registry,
        )
        self.OnlineStake = Gauge(
            "nano_node_online_stake_total", "Online Stake Total", registry=registry
        )
        self.PeersStake = Gauge(
            "nano_node_peers_stake_total", "Peers Stake Total", registry=registry
        )
        self.TrendedStake = Gauge(
            "nano_node_trended_stake_total", "Trended Stake Total", registry=registry
        )
        self.telemetry_raw_blocks = Gauge(
            "telemetry_raw_blocks",
            "Raw Telemetry block count by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_cemented = Gauge(
            "telemetry_raw_cemented",
            "Raw Telemetry cemented count by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_unchecked = Gauge(
            "telemetry_raw_unchecked",
            "Raw Telemetry unchecked count by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_accounts = Gauge(
            "telemetry_raw_accounts",
            "Raw Telemetry accounts count by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_bandwidth = Gauge(
            "telemetry_raw_bandwidth",
            "Raw Telemetry bandwidth cap by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_peers = Gauge(
            "telemetry_raw_peer",
            "Raw Telemetry peer count by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_protocol = Gauge(
            "telemetry_raw_protocol",
            "Raw Telemetry protocol version by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_major = Gauge(
            "telemetry_raw_major",
            "Raw Telemetry major version by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_minor = Gauge(
            "telemetry_raw_minor",
            "Raw Telemetry minor version by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_patch = Gauge(
            "telemetry_raw_patch",
            "Raw Telemetry patch version by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_pre = Gauge(
            "telemetry_raw_pre",
            "Raw Telemetry pre-release version by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_uptime = Gauge(
            "telemetry_raw_uptime",
            "Raw Telemetry uptime counter by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.telemetry_raw_maker = Gauge(
            "telemetry_raw_maker",
            "Raw Telemetry maker by endpoint",
            ["endpoint", "maker"],
            registry=registry,
        )
        self.telemetry_raw_timestamp = Gauge(
            "telemetry_raw_timestamp",
            "Raw Telemetry updated timestamp by endpoint",
            ["endpoint"],
            registry=registry,
        )
        self.network_raw_tx = Gauge(
            "network_raw_tx", "Raw tx from psutil", registry=registry
        )
        self.network_raw_rx = Gauge(
            "network_raw_rx", "Raw rx from psutil", registry=registry
        )

    def update(self, stats):
        self.ActiveDifficulty.set(stats.ActiveDifficulty)
        self.NetworkReceiveCurrent.set(stats.NetworkReceiveCurrent)
        self.Uptime.set(stats.Uptime)
        self.Frontiers.set(stats.Frontiers)

        if os.path.exists(self.config.node_data_path + "data.ldb"):
            self.databaseSize.labels("lmdb").set(
                os.path.getsize(self.config.node_data_path + "data.ldb")
            )
            self.databaseVolumeFree.set(
                psutil.disk_usage(self.config.node_data_path).free
            )
            self.databaseVolumeTotal.set(
                psutil.disk_usage(self.config.node_data_path).total
            )
            self.databaseVolumeUsed.set(
                psutil.disk_usage(self.config.node_data_path).used
            )

        self.QuorumDelta.set(stats.QuorumDelta)
        self.OnlineStake.set(stats.OnlineStake)
        self.PeersStake.set(stats.PeersStake)
        self.TrendedStake.set(stats.TrendedStake)
        self.PeersCount.set(len(stats.Peers["peers"]))

        for a in stats.BlockCount:
            self.BlockCount.labels(a).set(stats.BlockCount[a])

        for a in stats.TelemetryRaw or [] + [stats.Telemetry]:
            endpoint = telemetry_raw(a)

            self.telemetry_raw_blocks.labels(endpoint=endpoint.endpoint).set(
                endpoint.block_count
            )
            self.telemetry_raw_cemented.labels(endpoint=endpoint.endpoint).set(
                endpoint.cemented_count
            )
            self.telemetry_raw_unchecked.labels(endpoint=endpoint.endpoint).set(
                endpoint.unchecked_count
            )
            self.telemetry_raw_accounts.labels(endpoint=endpoint.endpoint).set(
                endpoint.account_count
            )
            self.telemetry_raw_bandwidth.labels(endpoint=endpoint.endpoint).set(
                endpoint.bandwidth_cap
            )
            self.telemetry_raw_peers.labels(endpoint=endpoint.endpoint).set(
                endpoint.peer_count
            )
            self.telemetry_raw_protocol.labels(endpoint=endpoint.endpoint).set(
                endpoint.protocol
            )
            self.telemetry_raw_major.labels(endpoint=endpoint.endpoint).set(
                endpoint.major
            )
            self.telemetry_raw_minor.labels(endpoint=endpoint.endpoint).set(
                endpoint.minor
            )
            self.telemetry_raw_patch.labels(endpoint=endpoint.endpoint).set(
                endpoint.patch
            )
            self.telemetry_raw_pre.labels(endpoint=endpoint.endpoint).set(
                endpoint.pre_release
            )
            self.telemetry_raw_uptime.labels(endpoint=endpoint.endpoint).set(
                endpoint.uptime
            )
            self.telemetry_raw_maker.labels(
                endpoint=endpoint.endpoint, maker=str(endpoint.maker)
            ).set(1)
            self.telemetry_raw_timestamp.labels(endpoint=endpoint.endpoint).set(
                endpoint.timestamp
            )

        # if int(stats.ConfirmationHistory["confirmation_stats"]["count"]) > 0:
        #     self.ConfirmationHistoryStats.labels("average").set(stats.ConfirmationHistory["confirmation_stats"]["average"])
        #     self.ConfirmationHistoryStats.labels("count").set(stats.ConfirmationHistory["confirmation_stats"]["count"])

        #     self.ConfirmationHistoryHist.clear()
        #     for conf in stats.ConfirmationHistory["confirmations"]:
        #         self.ConfirmationHistoryHist.labels("duration").observe(int(conf["duration"]) / 1000) # milliseconds to seconds

        for entry in stats.StatsCounters["entries"]:
            self.StatsCounters.labels(entry["type"], entry["detail"], entry["dir"]).set(
                entry["value"]
            )

        self.Version.info(
            {
                "rpc_version": stats.Version["rpc_version"],
                "store_version": stats.Version["store_version"],
                "protocol_version": stats.Version["protocol_version"],
                "node_vendor": stats.Version["node_vendor"],
                "store_vendor": stats.Version["store_vendor"],
                "network": stats.Version["network"],
                "network_identifier": stats.Version["network_identifier"],
                "build_info": stats.Version["build_info"],
            }
        )

        for l1 in stats.StatsObjects:
            for l2 in stats.StatsObjects[l1]:
                if "size" in stats.StatsObjects[l1][l2]:
                    self.StatsObjectsSize.labels(l1, l2).set(
                        stats.StatsObjects[l1][l2]["size"]
                    )
                    self.StatsObjectsCount.labels(l1, l2).set(
                        stats.StatsObjects[l1][l2]["count"]
                    )
                    if os.getenv("NANO_PROM_DEBUG"):
                        logging.debug(
                            "l2 %s %s %s %s",
                            l1,
                            l2,
                            stats.StatsObjects[l1][l2]["size"],
                            stats.StatsObjects[l1][l2]["count"],
                        )
                else:
                    for l3 in stats.StatsObjects[l1][l2]:
                        if "size" in stats.StatsObjects[l1][l2][l3]:
                            self.StatsObjectsSize.labels(f"{l1} : {l2}", l3).set(
                                stats.StatsObjects[l1][l2][l3]["size"]
                            )
                            self.StatsObjectsCount.labels(f"{l1} : {l2}", l3).set(
                                stats.StatsObjects[l1][l2][l3]["count"]
                            )
                            if os.getenv("NANO_PROM_DEBUG"):
                                logging.debug(
                                    "l3 %s %s %s %s %s",
                                    l1,
                                    l2,
                                    l3,
                                    stats.StatsObjects[l1][l2][l3]["size"],
                                    stats.StatsObjects[l1][l2][l3]["count"],
                                )
                        else: # Doing it this way is so wrong, but I'm tired and it works
                            for l4 in stats.StatsObjects[l1][l2][l3]:
                                if "size" in stats.StatsObjects[l1][l2][l3][l4]:
                                    self.StatsObjectsSize.labels(
                                        f"{l1} : {l2} : {l3}", l4
                                    ).set(stats.StatsObjects[l1][l2][l3][l4]["size"])
                                    self.StatsObjectsCount.labels(
                                        f"{l1} : {l2} : {l3}", l4
                                    ).set(stats.StatsObjects[l1][l2][l3][l4]["count"])
                                    if os.getenv("NANO_PROM_DEBUG"):
                                        logging.debug(
                                            "l4 %s %s %s %s %s %s",
                                            l1,
                                            l2,
                                            l3,
                                            l4,
                                            stats.StatsObjects[l1][l2][l3][l4]["size"],
                                            stats.StatsObjects[l1][l2][l3][l4]["count"],
                                        )

    @staticmethod
    def auth_handler(url, method, timeout, headers, data, creds):
        return basic_auth_handler(
            url, method, timeout, headers, data, creds["username"], creds["password"]
        )

    def pushStats(self, registry):
        for gateway, creds in self.config.push_gateway.items():
            if creds["username"] != "":

                def handle(url, method, timeout, headers, data):
                    return self.auth_handler(url, method, timeout, headers, data, creds)

                push_to_gateway(
                    gateway, job=self.config.hostname, registry=registry, handler=handle
                )
            else:
                push_to_gateway(
                    gateway,
                    job=self.config.runid,
                    grouping_key={"instance": self.config.hostname},
                    registry=registry,
                )
