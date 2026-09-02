"""
database/queries_users.py
Usuários — login, criação de contas (só admin) e listagem.
"""

from werkzeug.security import generate_password_hash, check_password_hash

from database.connection import execute_query


def get_user_by_username(username: str) -> dict | None:
    rows = execute_query("SELECT * FROM users WHERE username=%s", (username,))
    return dict(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> dict | None:
    rows = execute_query("SELECT * FROM users WHERE id=%s", (user_id,))
    return dict(rows[0]) if rows else None


def get_all_users() -> list:
    rows = execute_query("SELECT * FROM users ORDER BY id")
    return [dict(r) for r in (rows or [])]


def verify_login(username: str, password: str) -> dict | None:
    """Retorna o usuário se username/senha baterem e a conta estiver ativa."""
    user = get_user_by_username((username or "").strip())
    if not user or not user.get("active"):
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    return user


def create_user(username: str, password: str, email: str = None, full_name: str = None, is_admin: bool = False) -> int:
    username = (username or "").strip()
    if not username:
        raise ValueError("Nome de usuário é obrigatório.")
    if not password or len(password) < 6:
        raise ValueError("A senha precisa ter pelo menos 6 caracteres.")
    if get_user_by_username(username):
        raise ValueError("Já existe um usuário com esse nome.")
    rows = execute_query(
        """
        INSERT INTO users (username, password_hash, email, full_name, is_admin, active)
        VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
        """,
        (username, generate_password_hash(password), email or None, full_name or None, bool(is_admin)),
    )
    return rows[0]["id"] if rows else None


def set_user_active(user_id: int, active: bool):
    execute_query("UPDATE users SET active=%s WHERE id=%s", (bool(active), user_id), fetch=False)


def update_user_profile(user_id: int, email: str = None, full_name: str = None):
    execute_query(
        "UPDATE users SET email=%s, full_name=%s WHERE id=%s",
        (email or None, full_name or None, user_id), fetch=False,
    )


def update_user_password(user_id: int, new_password: str):
    if not new_password or len(new_password) < 6:
        raise ValueError("A senha precisa ter pelo menos 6 caracteres.")
    execute_query(
        "UPDATE users SET password_hash=%s WHERE id=%s",
        (generate_password_hash(new_password), user_id), fetch=False,
    )
