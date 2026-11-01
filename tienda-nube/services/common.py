"""Utilidades compartidas por los microservicios: BD, JWT, logs, salud y métricas."""
import json, os, socket, sqlite3, time, functools, logging, sys
from datetime import datetime, timezone
import jwt
from flask import Flask, g, request, jsonify

INSTANCE = socket.gethostname()
SERVICE = os.environ.get("SERVICE_NAME", "service")
DB_PATH = os.environ.get("DB_PATH", "/data/db.sqlite3")
STARTED = time.time()
_metrics = {"requests": 0, "errors_5xx": 0, "denied_4xx": 0}


def read_secret(name, default=None):
    """Lee un secreto montado por Docker en /run/secrets (nunca en el código)."""
    path = f"/run/secrets/{name}"
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name.upper(), default)


JWT_SECRET = read_secret("jwt_secret")
SERVICE_KEY = read_secret("service_key")

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(SERVICE)


def log_event(event, **fields):
    log.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "service": SERVICE, "instance": INSTANCE, "event": event, **fields},
                        ensure_ascii=False))


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        g.db = conn
    return g.db


def init_db(schema_sql, seed=None):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN IMMEDIATE")      # evita que dos workers inicialicen la BD al mismo tiempo
    for stmt in filter(str.strip, schema_sql.split(";")):
        conn.execute(stmt)
    if seed:
        seed(conn)
    conn.execute("COMMIT")
    conn.close()


def create_app():
    app = Flask(SERVICE)
    app.json.ensure_ascii = False

    @app.before_request
    def _start():
        g.t0 = time.perf_counter()

    @app.after_request
    def _after(resp):
        _metrics["requests"] += 1
        if resp.status_code >= 500:
            _metrics["errors_5xx"] += 1
        elif resp.status_code in (401, 403):
            _metrics["denied_4xx"] += 1
            log_event("access_denied", path=request.path, method=request.method,
                      status=resp.status_code, user=getattr(g, "user", {}).get("sub"),
                      ip=request.headers.get("X-Real-IP"))
        resp.headers["X-Instance"] = INSTANCE
        resp.headers["X-Service"] = SERVICE
        return resp

    @app.teardown_appcontext
    def _close(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/health")
    def health():
        try:
            get_db().execute("SELECT 1")
            db_ok = True
        except Exception:  # pragma: no cover
            db_ok = False
        return jsonify(status="UP" if db_ok else "DEGRADED", service=SERVICE, instance=INSTANCE,
                       database="OK" if db_ok else "ERROR", uptime_s=round(time.time() - STARTED)), \
            200 if db_ok else 503

    @app.get("/metrics")
    def metrics():
        return jsonify(service=SERVICE, instance=INSTANCE, **_metrics)

    return app


def require_auth(roles=None):
    """Autenticación (JWT válido) + autorización por rol (RBAC)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="No autenticado: falta el token"), 401
            try:
                g.user = jwt.decode(header[7:], JWT_SECRET, algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return jsonify(error="No autenticado: token vencido"), 401
            except jwt.InvalidTokenError:
                return jsonify(error="No autenticado: token inválido"), 401
            if roles and g.user.get("role") not in roles:
                return jsonify(error="No autorizado: su rol no permite esta acción"), 403
            return fn(*a, **kw)
        return wrapper
    return deco


def require_service_key(fn):
    """Endpoints internos: solo otros servicios con la llave de servicio."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if request.headers.get("X-Service-Key") != SERVICE_KEY:
            return jsonify(error="Servicio no autorizado"), 403
        return fn(*a, **kw)
    return wrapper


def simulated_latency():
    """Latencia de E/S simulada (p. ej. consulta a BD administrada remota)."""
    ms = int(os.environ.get("SIMULATED_LATENCY_MS", "0"))
    if ms:
        time.sleep(ms / 1000)
