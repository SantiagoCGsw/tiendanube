"""Servicio de productos: catálogo público y administración por el rol admin."""
from flask import request, jsonify
from common import create_app, init_db, get_db, require_auth, simulated_latency, log_event

SCHEMA = """
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  category TEXT NOT NULL, price_cop INTEGER NOT NULL, image TEXT, active INTEGER DEFAULT 1);
"""
SEED = [("SKU-001", "Audífonos inalámbricos", "Tecnología", 189900, "audifonos.svg"),
        ("SKU-002", "Morral antirrobo", "Accesorios", 129900, "morral.svg"),
        ("SKU-003", "Café de origen Huila 500 g", "Mercado", 38900, "cafe.svg"),
        ("SKU-004", "Teclado mecánico", "Tecnología", 249900, "teclado.svg"),
        ("SKU-005", "Botella térmica 750 ml", "Hogar", 59900, "botella.svg"),
        ("SKU-006", "Lámpara LED de escritorio", "Hogar", 89900, "lampara.svg")]


def seed(conn):
    conn.executemany("INSERT OR IGNORE INTO products(sku,name,category,price_cop,image) VALUES(?,?,?,?,?)", SEED)


init_db(SCHEMA, seed)
app = create_app()


@app.get("/api/products")
def list_products():
    simulated_latency()
    rows = get_db().execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/products/<int:pid>")
def get_product(pid):
    r = get_db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    return (jsonify(dict(r)), 200) if r else (jsonify(error="Producto no encontrado"), 404)


@app.post("/api/products")
@require_auth(roles={"admin"})
def create_product():
    d = request.get_json(silent=True) or {}
    try:
        price = int(d["price_cop"])
        assert price > 0 and d["name"].strip() and d["sku"].strip()
    except Exception:
        return jsonify(error="Datos de producto inválidos"), 400
    db = get_db()
    cur = db.execute("INSERT INTO products(sku,name,category,price_cop,image) VALUES(?,?,?,?,?)",
                     (d["sku"], d["name"], d.get("category", "General"), price, d.get("image")))
    db.commit()
    log_event("product_created", product_id=cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201
