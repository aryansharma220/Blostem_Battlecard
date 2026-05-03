import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings


DB_PATH = Path(settings.sqlite_path)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            competitor_name TEXT NOT NULL,
            canonical_domain TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            markdown TEXT,
            json_output TEXT,
            pdf_path TEXT,
            sources_json TEXT,
            snippets_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            progress INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            competitor_key TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            canonical_domain TEXT,
            markdown TEXT,
            json_output TEXT,
            pdf_path TEXT,
            sources_json TEXT,
            snippets_json TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def create_run(run_id: str, competitor_name: str) -> None:
    now = utcnow_iso()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO runs (id, competitor_name, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, competitor_name, "queued", now, now),
    )
    conn.commit()
    conn.close()


def update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utcnow_iso()
    assignments = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [run_id]

    conn = get_connection()
    conn.execute(f"UPDATE runs SET {assignments} WHERE id = ?", values)
    conn.commit()
    conn.close()


def reset_run(run_id: str) -> None:
    run = get_run(run_id)
    if run is None:
        return

    pdf_path = run.get("pdf_path")
    if pdf_path:
        try:
            Path(str(pdf_path)).unlink(missing_ok=True)
        except OSError:
            pass

    conn = get_connection()
    conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
    conn.execute(
        """
        UPDATE runs
        SET status = ?, error_message = NULL, canonical_domain = NULL, markdown = NULL,
            json_output = NULL, pdf_path = NULL, sources_json = NULL, snippets_json = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        ("queued", utcnow_iso(), run_id),
    )
    conn.commit()
    conn.close()


def delete_run(run_id: str) -> None:
    run = get_run(run_id)
    if run is None:
        return

    pdf_path = run.get("pdf_path")
    if pdf_path:
        try:
            Path(str(pdf_path)).unlink(missing_ok=True)
        except OSError:
            pass

    conn = get_connection()
    conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()


def add_event(run_id: str, stage: str, message: str, progress: int) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO events (run_id, stage, message, progress, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, stage, message, progress, utcnow_iso()),
    )
    conn.commit()
    conn.close()


def get_run(run_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None
    run = dict(row)

    events = [
        dict(e)
        for e in conn.execute(
            "SELECT stage, message, progress, created_at FROM events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
    ]
    conn.close()

    run["events"] = events
    for json_field in ("json_output", "sources_json", "snippets_json"):
        value = run.get(json_field)
        run[json_field] = json.loads(value) if value else None
    return run


def list_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, competitor_name, status, created_at, updated_at FROM runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_cache(
    competitor_key: str,
    run_id: str,
    canonical_domain: str | None,
    markdown: str,
    json_output: dict[str, Any],
    pdf_path: str | None,
    sources: list[dict[str, Any]],
    snippets: list[dict[str, Any]],
) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.cache_ttl_seconds)

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO cache_entries (
            competitor_key, run_id, canonical_domain, markdown, json_output, pdf_path,
            sources_json, snippets_json, created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(competitor_key) DO UPDATE SET
            run_id = excluded.run_id,
            canonical_domain = excluded.canonical_domain,
            markdown = excluded.markdown,
            json_output = excluded.json_output,
            pdf_path = excluded.pdf_path,
            sources_json = excluded.sources_json,
            snippets_json = excluded.snippets_json,
            created_at = excluded.created_at,
            expires_at = excluded.expires_at
        """,
        (
            competitor_key,
            run_id,
            canonical_domain,
            markdown,
            json.dumps(json_output),
            pdf_path,
            json.dumps(sources),
            json.dumps(snippets),
            now.isoformat(),
            expires_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_cache(competitor_key: str) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM cache_entries WHERE competitor_key = ?",
        (competitor_key,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    data = dict(row)
    expires_at = datetime.fromisoformat(data["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        return None

    data["json_output"] = json.loads(data["json_output"]) if data.get("json_output") else {}
    data["sources_json"] = json.loads(data["sources_json"]) if data.get("sources_json") else []
    data["snippets_json"] = json.loads(data["snippets_json"]) if data.get("snippets_json") else []
    return data
