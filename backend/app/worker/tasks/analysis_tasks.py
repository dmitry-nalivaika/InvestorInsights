# filepath: backend/app/worker/tasks/analysis_tasks.py
"""
Analysis pipeline Celery tasks.

Queue: ``analysis``

Tasks (implemented in later phases):
  - ``run_analysis`` — Execute analysis profile against a company
"""

from __future__ import annotations

from app.worker.celery_app import celery_app


@celery_app.task(
    name="app.worker.tasks.analysis_tasks.run_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    queue="analysis",
    acks_late=True,
)
def run_analysis(self, analysis_result_id: str) -> dict:
    """Execute an analysis profile against a company.

    Args:
        analysis_result_id: UUID of the AnalysisResult record.

    Returns:
        Dict with analysis outcome.
    """
    raise NotImplementedError("run_analysis task not yet implemented")
