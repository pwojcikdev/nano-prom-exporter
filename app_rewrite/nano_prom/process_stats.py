"""Local process and system statistics gathered via psutil.

All collection here is best-effort: the node process may be absent and some
data (per-thread CPU) is only available on Linux.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import psutil

log = logging.getLogger(__name__)


@dataclass
class ThreadCpu:
    pid: int
    tid: int
    name: str
    percent: float


@dataclass
class ProcessSnapshot:
    tx: int
    rx: int
    cpu: list[tuple[int, float]] = field(default_factory=list)  # (pid, cpu_percent)
    threads: list[ThreadCpu] = field(default_factory=list)


@dataclass
class DiskUsage:
    db_size: int
    total: int
    used: int
    free: int


def network_io() -> tuple[int, int]:
    counters = psutil.net_io_counters()
    return counters.bytes_sent, counters.bytes_recv


def find_node_processes(name: str = "nano_node") -> list[psutil.Process]:
    procs = []
    for proc in psutil.process_iter(attrs=["name", "pid"]):
        pname = proc.info.get("name")
        if pname and name in pname:
            procs.append(proc)
    return procs


def collect_process_snapshot(process_name: str = "nano_node") -> ProcessSnapshot:
    tx, rx = network_io()
    snapshot = ProcessSnapshot(tx=tx, rx=rx)
    for proc in find_node_processes(process_name):
        try:
            percent = proc.cpu_percent(interval=0.1)
            snapshot.cpu.append((proc.pid, percent))
            snapshot.threads.extend(_thread_cpu(proc, percent))
        except psutil.Error as e:
            log.debug("Skipping process %s: %r", getattr(proc, "pid", "?"), e)
    return snapshot


def collect_disk_usage(data_path: Path) -> DiskUsage | None:
    """DB file size and volume usage, or None if the node's data.ldb is absent."""
    db_file = data_path / "data.ldb"
    if not db_file.exists():
        return None
    usage = psutil.disk_usage(str(data_path))
    return DiskUsage(
        db_size=db_file.stat().st_size,
        total=usage.total,
        used=usage.used,
        free=usage.free,
    )


def _thread_cpu(proc: psutil.Process, process_percent: float) -> list[ThreadCpu]:
    """Split a process's CPU% across its threads, weighted by cumulative CPU time.

    Thread names are only exposed via /proc, so this is Linux-only and returns
    nothing on other platforms.
    """
    if not sys.platform.startswith("linux"):
        return []
    total_time = sum(proc.cpu_times())
    if total_time <= 0:
        return []
    result = []
    for tid, name, thread_time in _read_proc_threads(proc.pid):
        result.append(
            ThreadCpu(proc.pid, tid, name, process_percent * (thread_time / total_time))
        )
    return result


def _read_proc_threads(pid: int):
    """Yield ``(tid, name, cpu_seconds)`` for each thread of ``pid`` via /proc."""
    clock_ticks = os.sysconf("SC_CLK_TCK")
    task_dir = Path("/proc") / str(pid) / "task"
    for tid_dir in task_dir.iterdir():
        try:
            data = (tid_dir / "stat").read_text().strip()
        except FileNotFoundError:
            continue  # thread vanished between listing and read
        # comm is wrapped in parentheses and may itself contain them.
        name = data[data.find("(") + 1 : data.rfind(")")]
        fields = data[data.rfind(")") + 2 :].split(" ")
        utime = float(fields[11]) / clock_ticks
        stime = float(fields[12]) / clock_ticks
        yield int(tid_dir.name), name, utime + stime
