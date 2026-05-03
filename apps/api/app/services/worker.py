from __future__ import annotations

from dataclasses import dataclass, field
from queue import Queue
from typing import Any


@dataclass
class PipelineJob:
    run_id: str
    competitor_name: str
    max_retries: int = 2
    payload: dict[str, Any] = field(default_factory=dict)


class WorkerPool:
    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self.queue: Queue[PipelineJob] = Queue()

    def submit(self, job: PipelineJob) -> None:
        self.queue.put(job)

    def pending_jobs(self) -> int:
        return self.queue.qsize()
