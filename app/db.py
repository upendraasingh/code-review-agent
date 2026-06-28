import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "reviews.db"
connection = sqlite3.connect(DB_PATH, check_same_thread=False)
connection.row_factory = sqlite3.Row


def _ensure_column(column_name: str, column_type: str) -> None:
    existing_columns = [row[1] for row in connection.execute("PRAGMA table_info(reviews)")]
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE reviews ADD COLUMN {column_name} {column_type}")
        connection.commit()


def _init_db() -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            pr_url TEXT,
            title TEXT,
            body TEXT,
            diff TEXT,
            status TEXT NOT NULL,
            security_findings TEXT,
            performance_findings TEXT,
            style_findings TEXT,
            summary_comment TEXT,
            overall_score INTEGER NOT NULL DEFAULT 0,
            language TEXT,
            filename TEXT,
            code_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    _ensure_column("overall_score", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column("language", "TEXT")
    _ensure_column("filename", "TEXT")
    _ensure_column("code_text", "TEXT")


def _serialize_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def _deserialize_list(value: str | None) -> list[str]:
    if not value:
        return []
    return json.loads(value)


def create_review(
    source: str,
    repo_name: str,
    pr_number: int,
    title: str,
    body: str,
    diff: str,
    pr_url: str,
    status: str = "pending",
    security_findings: list[str] | None = None,
    performance_findings: list[str] | None = None,
    style_findings: list[str] | None = None,
    summary_comment: str = "",
    overall_score: int = 0,
    language: str | None = None,
    filename: str | None = None,
    code_text: str | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    cursor = connection.execute(
        """
        INSERT INTO reviews (
            source, repo_name, pr_number, pr_url, title, body, diff, status,
            security_findings, performance_findings, style_findings, summary_comment,
            overall_score, language, filename, code_text, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            repo_name,
            pr_number,
            pr_url,
            title,
            body,
            diff,
            status,
            _serialize_list(security_findings or []),
            _serialize_list(performance_findings or []),
            _serialize_list(style_findings or []),
            summary_comment,
            overall_score,
            language,
            filename,
            code_text,
            now,
            now,
        ),
    )
    connection.commit()
    return cursor.lastrowid


def update_review_results(
    review_id: int,
    security_findings: list[str],
    performance_findings: list[str],
    style_findings: list[str],
    summary_comment: str,
    status: str = "complete",
    overall_score: int | None = None,
) -> None:
    now = datetime.utcnow().isoformat()
    query = """
        UPDATE reviews
        SET security_findings = ?, performance_findings = ?, style_findings = ?,
            summary_comment = ?, status = ?, updated_at = ?
    """
    params = [
        _serialize_list(security_findings),
        _serialize_list(performance_findings),
        _serialize_list(style_findings),
        summary_comment,
        status,
        now,
    ]
    if overall_score is not None:
        query += ", overall_score = ?"
        params.append(overall_score)
    query += " WHERE id = ?"
    params.append(review_id)

    connection.execute(query, tuple(params))
    connection.commit()


def get_all_reviews() -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM reviews ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "source": row["source"],
        "repo_name": row["repo_name"],
        "pr_number": row["pr_number"],
        "pr_url": row["pr_url"],
        "title": row["title"],
        "body": row["body"],
        "diff": row["diff"],
        "status": row["status"],
        "security_findings": _deserialize_list(row["security_findings"]),
        "performance_findings": _deserialize_list(row["performance_findings"]),
        "style_findings": _deserialize_list(row["style_findings"]),
        "summary_comment": row["summary_comment"],
        "overall_score": row["overall_score"],
        "language": row["language"],
        "filename": row["filename"],
        "code_text": row["code_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_init_db()
