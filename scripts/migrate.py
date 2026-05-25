"""Database migration script.

Applies database/schema.sql (and any future migration files) to the target
Postgres database.  Run this BEFORE starting the application on every deploy.

Usage::

    # Using the DSN from .env
    python scripts/migrate.py

    # Explicit DSN
    python scripts/migrate.py --dsn "postgresql://user:pass@host:5432/dbname"

In CI/CD or Kubernetes, run this as a pre-deploy job / init container before
the application container starts.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = REPO_ROOT / "database" / "schema.sql"
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def _load_settings_dsn() -> str:
    """Read POSTGRES_DSN from the project .env / environment via pydantic-settings."""
    from mainframe_doc_orchestrator.settings import get_settings
    return get_settings().postgres_dsn


def apply_sql_file(conn, path: Path) -> None:
    """Execute every statement in a .sql file against an open connection."""
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Applied: %s", path.name)


def run(dsn: str) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg[binary] is required: pip install psycopg[binary]") from exc

    with psycopg.connect(dsn) as conn:
        # 1. Apply base schema (idempotent).
        apply_sql_file(conn, SCHEMA_FILE)

        # 2. Apply any ordered migration files under database/migrations/, if present.
        if MIGRATIONS_DIR.is_dir():
            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for migration in migration_files:
                apply_sql_file(conn, migration)

    logger.info("Migration complete.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    parser = argparse.ArgumentParser(description="Apply Postgres schema and migrations.")
    parser.add_argument(
        "--dsn",
        default=None,
        help="Postgres DSN (default: read POSTGRES_DSN from environment / .env)",
    )
    args = parser.parse_args()

    dsn = args.dsn or _load_settings_dsn()
    if not dsn:
        logger.error("POSTGRES_DSN is not set. Pass --dsn or set it in .env.")
        sys.exit(1)

    run(dsn)


if __name__ == "__main__":
    main()
