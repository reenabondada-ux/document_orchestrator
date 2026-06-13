"""Async Postgres repositories for document runs and retrieval passes.

Both classes accept a ``psycopg_pool.AsyncConnectionPool`` which is created
once during the application lifespan (see ``api/app.py``) and injected via
``api/dependencies.py``.  All public methods are async and must be awaited.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import psycopg_pool


class PostgresDocumentRepository:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_run(
        self,
        *,
        run_id: str,
        document_title: str,
        system_id: str,
        plan: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO document_runs (run_id, document_title, system_id, plan, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING run_id, document_title, system_id, plan, status, created_at, completed_at, export_artifact
                    """,
                    (run_id, document_title, system_id, json.dumps(plan), status),
                )
                row = await cur.fetchone()
            await conn.commit()
        return self._row_to_run(row)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT run_id, document_title, system_id, plan, status, created_at, completed_at, export_artifact
                    FROM document_runs
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Document run not found: {run_id}")
        return self._row_to_run(row)

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT run_id, document_title, system_id, plan, status, created_at, completed_at, export_artifact
                    FROM document_runs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cur.fetchall() or []
        return [self._row_to_run(row) for row in rows]

    async def update_run(
        self,
        run_id: str,
        *,
        plan: dict[str, Any] | None = None,
        status: str | None = None,
        completed_at: str | None = None,
        export_artifact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields: list[str] = []
        values: list[Any] = []
        if plan is not None:
            fields.append("plan = %s")
            values.append(json.dumps(plan))
        if status is not None:
            fields.append("status = %s")
            values.append(status)
        if completed_at is not None:
            fields.append("completed_at = %s")
            values.append(completed_at)
        if export_artifact is not None:
            fields.append("export_artifact = %s")
            values.append(json.dumps(export_artifact))
        if not fields:
            return await self.get_run(run_id)
        values.append(run_id)
        sql = f"UPDATE document_runs SET {', '.join(fields)} WHERE run_id = %s RETURNING run_id, document_title, system_id, plan, status, created_at, completed_at, export_artifact"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                # Row-level lock to serialize concurrent writers for this run.
                await cur.execute(
                    """
                    SELECT run_id
                    FROM document_runs
                    WHERE run_id = %s
                    FOR UPDATE
                    """,
                    (run_id,),
                )
                locked = await cur.fetchone()
                if locked is None:
                    raise KeyError(f"Document run not found: {run_id}")

                await cur.execute(sql, values)
                row = await cur.fetchone()
            await conn.commit()
        return self._row_to_run(row)

    async def get_sections(self, run_id: str) -> list[dict[str, Any]]:
        run = await self.get_run(run_id)
        return list(run["plan"].get("sections", []))

    async def get_section(self, run_id: str, section_name: str) -> dict[str, Any]:
        sections = await self.get_sections(run_id)
        for section in sections:
            if section.get("section_name") == section_name:
                return section
        raise KeyError(f"Section not found: {section_name}")

    @staticmethod
    def _row_to_run(row: Any) -> dict[str, Any]:
        if row is None:
            raise KeyError("Expected row, got None")
        keys = [
            "run_id",
            "document_title",
            "system_id",
            "plan",
            "status",
            "created_at",
            "completed_at",
            "export_artifact",
        ]
        data = dict(zip(keys, row)) if not isinstance(row, dict) else row
        # psycopg returns JSONB columns as Python dicts; ensure plan is always a dict
        if isinstance(data.get("plan"), str):
            import json as _json

            data["plan"] = _json.loads(data["plan"])
        return data


class RetrievalPassRepository:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def next_pass_number(self, run_id: str, section_name: str) -> int:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT COALESCE(MAX(pass_number), 0)
                    FROM retrieval_passes
                    WHERE run_id = %s AND section_name = %s
                    """,
                    (run_id, section_name),
                )
                row = await cur.fetchone()
        return int(row[0] or 0) + 1

    async def create_pass(
        self,
        *,
        run_id: str,
        section_name: str,
        pass_number: int,
        query: str,
        evidence_request_id: str | None,
        status: str,
    ) -> dict[str, Any]:
        pass_id = str(uuid4())
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO retrieval_passes (pass_id, run_id, section_name, pass_number, query, evidence_request_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING pass_id, run_id, section_name, pass_number, query, evidence_request_id, status, created_at
                    """,
                    (
                        pass_id,
                        run_id,
                        section_name,
                        pass_number,
                        query,
                        evidence_request_id,
                        status,
                    ),
                )
                row = await cur.fetchone()
            await conn.commit()
        return self._row_to_pass(row)

    async def complete_pass(
        self, *, pass_id: str, evidence_request_id: str, status: str = "completed"
    ) -> dict[str, Any]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE retrieval_passes
                    SET evidence_request_id = %s, status = %s
                    WHERE pass_id = %s
                    RETURNING pass_id, run_id, section_name, pass_number, query, evidence_request_id, status, created_at
                    """,
                    (evidence_request_id, status, pass_id),
                )
                row = await cur.fetchone()
            await conn.commit()
        return self._row_to_pass(row)

    async def get_latest_completed_pass(
        self, run_id: str, section_name: str
    ) -> dict[str, Any] | None:
        """Return the most recent completed pass for a section that has an
        evidence_request_id, or None if no such pass exists.

        Used for crash recovery: if retrieval completed but draft writing did
        not, we can re-fetch the evidence pack instead of re-triggering retrieval.
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT pass_id, run_id, section_name, pass_number, query, evidence_request_id, status, created_at
                    FROM retrieval_passes
                    WHERE run_id = %s
                      AND section_name = %s
                      AND status = 'completed'
                      AND evidence_request_id IS NOT NULL
                    ORDER BY pass_number DESC
                    LIMIT 1
                    """,
                    (run_id, section_name),
                )
                row = await cur.fetchone()
        return self._row_to_pass(row) if row else None

    async def list_passes_for_run(self, run_id: str) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT pass_id, run_id, section_name, pass_number, query, evidence_request_id, status, created_at
                    FROM retrieval_passes
                    WHERE run_id = %s
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                )
                rows = await cur.fetchall() or []
        return [self._row_to_pass(row) for row in rows]

    @staticmethod
    def _row_to_pass(row: Any) -> dict[str, Any]:
        if row is None:
            raise KeyError("Expected row, got None")
        keys = [
            "pass_id",
            "run_id",
            "section_name",
            "pass_number",
            "query",
            "evidence_request_id",
            "status",
            "created_at",
        ]
        data = dict(zip(keys, row)) if not isinstance(row, dict) else row
        return data
