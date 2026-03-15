# -*- coding: utf-8 -*-
"""Execution history repository for cron jobs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..models import CronExecutionRecord, ExecutionHistoryFile


class ExecutionHistoryRepository:
    """File-based repository for cron job execution history.

    Stores execution records in a separate JSON file.
    Automatically trims old records to keep only recent N per job.
    """

    def __init__(self, path: Path, max_records_per_job: int = 100):
        self._path = path.expanduser()
        self._max_records_per_job = max_records_per_job

    @property
    def path(self) -> Path:
        return self._path

    async def load(self) -> ExecutionHistoryFile:
        """Load execution history from file."""
        if not self._path.exists():
            return ExecutionHistoryFile(
                version=1,
                records=[],
                max_records=self._max_records_per_job,
            )

        data = json.loads(self._path.read_text(encoding="utf-8"))
        return ExecutionHistoryFile.model_validate(data)

    async def save(self, history_file: ExecutionHistoryFile) -> None:
        """Persist execution history to file (atomic write)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = history_file.model_dump(mode="json")

        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self._path)

    async def add_record(self, record: CronExecutionRecord) -> None:
        """Add a new execution record and trim old records."""
        history = await self.load()

        # Generate ID if not set
        if not record.id:
            record.id = str(uuid.uuid4())

        history.records.append(record)

        # Trim old records per job (keep only recent N)
        job_records: Dict[str, List[CronExecutionRecord]] = {}
        for r in history.records:
            if r.job_id not in job_records:
                job_records[r.job_id] = []
            job_records[r.job_id].append(r)

        trimmed_records: List[CronExecutionRecord] = []
        for job_id, records in job_records.items():
            # Sort by triggered_at descending, keep top N
            sorted_records = sorted(
                records,
                key=lambda x: x.triggered_at,
                reverse=True,
            )[: self._max_records_per_job]
            trimmed_records.extend(sorted_records)

        history.records = trimmed_records
        await self.save(history)

    async def update_record(self, record: CronExecutionRecord) -> None:
        """Update an existing execution record."""
        history = await self.load()

        for i, r in enumerate(history.records):
            if r.id == record.id:
                history.records[i] = record
                break
        else:
            # If not found, add as new record
            history.records.append(record)

        await self.save(history)

    async def get_records_by_job(
        self,
        job_id: str,
        limit: int = 50,
    ) -> List[CronExecutionRecord]:
        """Get execution records for a specific job."""
        history = await self.load()
        job_records = [r for r in history.records if r.job_id == job_id]
        # Sort by triggered_at descending
        sorted_records = sorted(
            job_records,
            key=lambda x: x.triggered_at,
            reverse=True,
        )
        return sorted_records[:limit]

    async def get_recent_records(
        self,
        limit: int = 100,
    ) -> List[CronExecutionRecord]:
        """Get most recent execution records across all jobs."""
        history = await self.load()
        sorted_records = sorted(
            history.records,
            key=lambda x: x.triggered_at,
            reverse=True,
        )
        return sorted_records[:limit]

    async def delete_records_by_job(self, job_id: str) -> int:
        """Delete all execution records for a job. Returns count deleted."""
        history = await self.load()
        before = len(history.records)
        history.records = [r for r in history.records if r.job_id != job_id]
        deleted = before - len(history.records)
        await self.save(history)
        return deleted
