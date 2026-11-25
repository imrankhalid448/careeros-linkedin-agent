import sqlite3
from contextlib import contextmanager
from app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT DEFAULT '',
                headline TEXT DEFAULT '',
                about TEXT DEFAULT '',
                skills_json TEXT DEFAULT '[]',
                experience_json TEXT DEFAULT '[]',
                portfolio_links_json TEXT DEFAULT '[]',
                target_roles_json TEXT DEFAULT '["AI Engineer", "ML Engineer", "Computer Vision Engineer", "Generative AI Engineer"]',
                preferred_locations_json TEXT DEFAULT '[]',
                work_preferences TEXT DEFAULT '',
                work_authorization TEXT DEFAULT '',
                cv_filename TEXT DEFAULT '',
                cv_raw_text TEXT DEFAULT '',
                linkedin_raw_text TEXT DEFAULT '',
                voice_notes TEXT DEFAULT '',
                confirmed INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            INSERT OR IGNORE INTO user_profile (id) VALUES (1);

            CREATE TABLE IF NOT EXISTS project_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                github_url TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT 'linkedin',
                source_type TEXT DEFAULT 'idea',
                source_ref TEXT DEFAULT '',
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                scheduled_for TEXT DEFAULT '',
                idempotency_key TEXT UNIQUE NOT NULL,
                external_post_id TEXT DEFAULT '',
                external_post_url TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                ai_provider_used TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                image_prompt TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                published_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT 'linkedin',
                target_url TEXT DEFAULT '',
                target_urn TEXT DEFAULT '',
                source_post_text TEXT DEFAULT '',
                draft_reply TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                idempotency_key TEXT UNIQUE NOT NULL,
                external_comment_id TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                ai_provider_used TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                image_prompt TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                published_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT DEFAULT '',
                location TEXT DEFAULT '',
                work_mode TEXT DEFAULT 'unknown',
                sponsorship TEXT DEFAULT 'unknown',
                apply_url TEXT DEFAULT '',
                source_type TEXT DEFAULT 'pasted',
                raw_text TEXT NOT NULL,
                match_score INTEGER DEFAULT 0,
                match_reasons_json TEXT DEFAULT '[]',
                gaps_json TEXT DEFAULT '[]',
                constraints_json TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'Saved',
                cv_edits_suggestion TEXT DEFAULT '',
                cover_letter_draft TEXT DEFAULT '',
                screening_qa_json TEXT DEFAULT '[]',
                ai_provider_used TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS platform_credentials (
                platform TEXT PRIMARY KEY,
                encrypted_payload TEXT NOT NULL,
                account_label TEXT DEFAULT '',
                external_user_id TEXT DEFAULT '',
                scopes_json TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                cards_json TEXT DEFAULT '[]',
                ai_provider_used TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(posts)").fetchall()}
        if "image_path" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN image_path TEXT DEFAULT ''")
        if "image_prompt" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN image_prompt TEXT DEFAULT ''")
