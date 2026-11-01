"""Servicio de inventario: existencias y reserva atómica de unidades."""
from flask import request, jsonify, g
from common import (create_app, init_db, get_db, require_auth, require_service_key, log_event)

SCHEMA = """
CREATE TABLE IF NOT EXISTS stock(
  product_id INTEGER PRIMARY KEY, quantity INTEGER NOT NULL CHECK(quantity >= 0),
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def seed(conn):
    conn.executemany("INSERT OR IGNORE INTO stock(product_id,quantity) VALUES(?,?)",
                     [(1, 50), (2, 30), (3, 120), (4, 15), (5, 60), (6, 3)])


init_db(SCHEMA, seed)
app = create_app()


@app.get("/api/inventory")
@require_auth(roles={"admin", "operador"})
def list_stock():
    return jsonify([dict(r) for r in get_db().execute("SELECT * FROM stock ORDER BY product_id")])


@app.put("/api/inventory/<int:pid>")
@require_auth(roles={"admin", "operador"})
def set_stock(pid):
    d = request.get_json(silent=True) or {}
    qty = d.get("quantity")
    if not isinstance(qty, int) or qty < 0:
        return jsonify(error="Cantidad inválida"), 400
    db = get_db()
    db.execute("INSERT INTO stock(product_id,quantity) VALUES(?,?) ON CONFLICT(product_id) "
               "DO UPDATE SET quantity=excluded.quantity, updated_at=CURRENT_TIMESTAMP", (pid, qty))
    db.commit()
    log_event("stock_updated", product_id=pid, quantity=qty, by=g.user["sub"])
    return jsonify(product_id=pid, quantity=qty)


@app.post("/internal/inventory/reserve")
@require_service_key
def reserve():
    """Reserva todas las unidades de un pedido en una sola transacción (todo o nada)."""
    items = (request.get_json(silent=True) or {}).get("items", [])
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    for it in items:
        row = db.execute("SELECT quantity FROM stock WHERE product_id=?", (it["product_id"],)).fetchone()
        if not row or row["quantity"] < it["qty"]:
            db.rollback()
            return jsonify(error=f"Sin existencias suficientes del producto {it['product_id']}"), 409
    for it in items:
        db.execute("UPDATE stock SET quantity=quantity-?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?",
                   (it["qty"], it["product_id"]))
    db.commit()
    log_event("stock_reserved", items=items)
    return jsonify(reserved=True)
