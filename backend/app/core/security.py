import json
from cryptography.fernet import Fernet
from app.config import KEY_FILE
from app.database import db_session


def _get_fernet() -> Fernet:
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
    return Fernet(key)


def save_platform_credentials(
    platform: str,
    payload: dict,
    account_label: str = "",
    external_user_id: str = "",
    scopes: list[str] | None = None,
) -> None:
    token = _get_fernet().encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO platform_credentials (platform, encrypted_payload, account_label, external_user_id, scopes_json, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(platform) DO UPDATE SET
                encrypted_payload = excluded.encrypted_payload,
                account_label = excluded.account_label,
                external_user_id = excluded.external_user_id,
                scopes_json = excluded.scopes_json,
                updated_at = datetime('now')
            """,
            (platform, token, account_label, external_user_id, json.dumps(scopes or [])),
        )


def load_platform_credentials(platform: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM platform_credentials WHERE platform = ?", (platform,)
        ).fetchone()
    if not row:
        return None
    decrypted = _get_fernet().decrypt(row["encrypted_payload"].encode("utf-8")).decode("utf-8")
    data = json.loads(decrypted)
    return {
        "payload": data,
        "account_label": row["account_label"],
        "external_user_id": row["external_user_id"],
        "scopes": json.loads(row["scopes_json"] or "[]"),
        "updated_at": row["updated_at"],
    }


def delete_platform_credentials(platform: str) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM platform_credentials WHERE platform = ?", (platform,))
