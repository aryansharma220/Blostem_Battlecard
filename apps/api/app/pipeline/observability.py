"""Pipeline observability and timing utilities.

Provides utilities for:
- Measuring stage completion times
- Logging pipeline progress
- Asserting timing budgets
- Collecting pipeline metrics
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from app.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class StageTiming:
    """Timing information for a pipeline stage."""
    stage_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_sec: Optional[float] = None
    error_message: Optional[str] = None
    
    def complete(self, error_message: Optional[str] = None) -> float:
        """Mark stage as complete and return duration."""
        self.end_time = time.time()
        self.duration_sec = self.end_time - self.start_time
        self.error_message = error_message
        return self.duration_sec


@dataclass
class PipelineMetrics:
    """Metrics collected during a pipeline run."""
    run_id: str
    competitor_name: str
    start_time: float
    stages: dict[str, StageTiming] = field(default_factory=dict)
    end_time: Optional[float] = None
    total_duration_sec: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    sources_discovered: int = 0
    sources_crawled: int = 0
    snippets_extracted: int = 0
    signals_generated: int = 0
    
    def stage_start(self, stage_name: str) -> StageTiming:
        """Start timing a stage."""
        stage = StageTiming(stage_name=stage_name, start_time=time.time())
        self.stages[stage_name] = stage
        logger.info(f"Pipeline {self.run_id}: Starting {stage_name}")
        return stage
    
    def stage_complete(self, stage_name: str, error_message: Optional[str] = None) -> float:
        """Mark a stage as complete."""
        if stage_name not in self.stages:
            logger.warning(f"Pipeline {self.run_id}: Stage {stage_name} was never started")
            return 0.0
        
        duration = self.stages[stage_name].complete(error_message)
        status = f"completed in {duration:.1f}s" if not error_message else f"failed: {error_message}"
        logger.info(f"Pipeline {self.run_id}: {stage_name} {status}")
        return duration
    
    def complete(self, success: bool = True, error_message: Optional[str] = None) -> float:
        """Mark the entire pipeline as complete."""
        self.end_time = time.time()
        self.total_duration_sec = self.end_time - self.start_time
        self.success = success
        self.error_message = error_message
        
        status = "completed" if success else f"failed: {error_message}"
        logger.info(
            f"Pipeline {self.run_id}: {status} in {self.total_duration_sec:.1f}s total, "
            f"discovered={self.sources_discovered}, crawled={self.sources_crawled}, "
            f"snippets={self.snippets_extracted}, signals={self.signals_generated}"
        )
        return self.total_duration_sec
    
    def stage_summary(self) -> str:
        """Return a formatted summary of stage timings."""
        lines = [f"Pipeline {self.run_id} stage breakdown (total {self.total_duration_sec:.1f}s):"]
        for stage_name, timing in self.stages.items():
            if timing.duration_sec is not None:
                pct = (timing.duration_sec / self.total_duration_sec * 100) if self.total_duration_sec else 0
                status = "✓" if not timing.error_message else "✗"
                lines.append(f"  {status} {stage_name}: {timing.duration_sec:.1f}s ({pct:.0f}%)")
        return "\n".join(lines)
    
    def assert_timing_budget(self, stage_name: str, max_duration_sec: float) -> bool:
        """Assert that a stage completed within the time budget."""
        if stage_name not in self.stages:
            logger.warning(f"Pipeline {self.run_id}: Stage {stage_name} not found in metrics")
            return False
        
        stage = self.stages[stage_name]
        if stage.duration_sec is None:
            logger.warning(f"Pipeline {self.run_id}: Stage {stage_name} did not complete")
            return False
        
        if stage.duration_sec > max_duration_sec:
            logger.warning(
                f"Pipeline {self.run_id}: Stage {stage_name} exceeded budget: "
                f"{stage.duration_sec:.1f}s > {max_duration_sec}s"
            )
            return False
        
        logger.debug(
            f"Pipeline {self.run_id}: Stage {stage_name} within budget: "
            f"{stage.duration_sec:.1f}s <= {max_duration_sec}s"
        )
        return True


def format_pipeline_report(metrics: PipelineMetrics) -> str:
    """Format a complete pipeline execution report."""
    report_lines = [
        f"\n{'='*70}",
        f"Pipeline Report: {metrics.run_id}",
        f"{'='*70}",
        f"Competitor: {metrics.competitor_name}",
        f"Status: {'SUCCESS' if metrics.success else 'FAILED'}",
        f"Total Duration: {metrics.total_duration_sec:.1f}s",
        f"",
        f"Discovery & Crawl:",
        f"  Sources discovered: {metrics.sources_discovered}",
        f"  Sources successfully crawled: {metrics.sources_crawled}",
        f"  Crawl success rate: {metrics.sources_crawled/max(metrics.sources_discovered, 1)*100:.0f}%",
        f"",
        f"Processing:",
        f"  Snippets extracted: {metrics.snippets_extracted}",
        f"  Signals generated: {metrics.signals_generated}",
        f"",
        metrics.stage_summary(),
        f"{'='*70}",
    ]
    return "\n".join(report_lines)


# Global metrics storage for current run (for monitoring/debugging)
_current_metrics: Optional[PipelineMetrics] = None


def get_current_metrics() -> Optional[PipelineMetrics]:
    """Get the metrics object for the current pipeline run."""
    return _current_metrics


def set_current_metrics(metrics: PipelineMetrics) -> None:
    """Set the metrics object for the current pipeline run."""
    global _current_metrics
    _current_metrics = metrics


def clear_current_metrics() -> None:
    """Clear the metrics object (e.g., on run completion)."""
    global _current_metrics
    _current_metrics = None
