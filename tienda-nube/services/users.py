"""Servicio de usuarios: registro, inicio de sesión (JWT) y gestión de cuentas."""
import re, time
import bcrypt, jwt
from flask import request, jsonify, g
from common import create_app, init_db, get_db, require_auth, JWT_SECRET, read_secret, log_event

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'cliente',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""
ROLES = {"cliente", "operador", "admin"}


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def seed(conn):
    admin_pw = read_secret("admin_password", "Admin#2026")
    for name, email, pw, role in [
        ("Administrador", "admin@tienda.co", admin_pw, "admin"),
        ("Operador Inventario", "operador@tienda.co", "Operador#2026", "operador"),
        ("Cliente A", "cliente.a@correo.co", "ClienteA#2026", "cliente"),
        ("Cliente B", "cliente.b@correo.co", "ClienteB#2026", "cliente")]:
        if not conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            conn.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                         (name, email, _hash(pw), role))


init_db(SCHEMA, seed)
app = create_app()


@app.post("/api/users/register")
def register():
    d = request.get_json(silent=True) or {}
    name, email, pw = d.get("name", "").strip(), d.get("email", "").strip().lower(), d.get("password", "")
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Nombre o correo inválido"), 400
    if len(pw) < 8 or not re.search(r"\d", pw) or not re.search(r"[A-Za-z]", pw):
        return jsonify(error="La contraseña debe tener mínimo 8 caracteres, letras y números"), 400
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return jsonify(error="El correo ya está registrado"), 409
    cur = db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?, 'cliente')",
                     (name, email, _hash(pw)))
    db.commit()
    log_event("user_registered", user_id=cur.lastrowid)
    return jsonify(id=cur.lastrowid, name=name, email=email, role="cliente"), 201


@app.post("/api/users/login")
def login():
    d = request.get_json(silent=True) or {}
    email, pw = d.get("email", "").strip().lower(), d.get("password", "")
    row = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not bcrypt.checkpw(pw.encode(), row["password_hash"].encode()):
        log_event("login_failed", email=email, ip=request.headers.get("X-Real-IP"))
        return jsonify(error="Credenciales inválidas"), 401
    now = int(time.time())
    token = jwt.encode({"sub": str(row["id"]), "name": row["name"], "role": row["role"],
                        "iat": now, "exp": now + 1800}, JWT_SECRET, algorithm="HS256")
    log_event("login_ok", user_id=row["id"], role=row["role"])
    return jsonify(access_token=token, token_type="Bearer", expires_in=1800,
                   user={"id": row["id"], "name": row["name"], "role": row["role"]})


@app.get("/api/users/me")
@require_auth()
def me():
    row = get_db().execute("SELECT id,name,email,role,created_at FROM users WHERE id=?",
                           (g.user["sub"],)).fetchone()
    return jsonify(dict(row))


@app.get("/api/users")
@require_auth(roles={"admin"})
def list_users():
    rows = get_db().execute("SELECT id,name,email,role,created_at FROM users").fetchall()
    return jsonify([dict(r) for r in rows])
