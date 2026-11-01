"""Servicio de pedidos: crea pedidos validando precio y existencias con otros servicios."""
import json, os, uuid
import requests
from flask import request, jsonify, g
from common import (create_app, init_db, get_db, require_auth, SERVICE_KEY, log_event)

PRODUCTS_URL = os.environ.get("PRODUCTS_URL", "http://products:5000")
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://inventory:5000")
SCHEMA = """
CREATE TABLE IF NOT EXISTS orders(
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, items TEXT NOT NULL, total_cop INTEGER NOT NULL,
  status TEXT NOT NULL, payment_status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""
init_db(SCHEMA)
app = create_app()


@app.post("/api/orders")
@require_auth(roles={"cliente"})
def create_order():
    items = (request.get_json(silent=True) or {}).get("items", [])
    if not items or any(int(i.get("qty", 0)) <= 0 for i in items):
        return jsonify(error="El pedido debe tener productos con cantidad positiva"), 400
    detail, total = [], 0
    for it in items:   # el precio se consulta al servicio de productos, no se confía en el cliente
        r = requests.get(f"{PRODUCTS_URL}/api/products/{int(it['product_id'])}", timeout=3)
        if r.status_code != 200:
            return jsonify(error=f"Producto {it['product_id']} no existe"), 404
        p = r.json()
        detail.append({"product_id": p["id"], "name": p["name"], "qty": int(it["qty"]),
                       "unit_price_cop": p["price_cop"]})
        total += p["price_cop"] * int(it["qty"])
    r = requests.post(f"{INVENTORY_URL}/internal/inventory/reserve", timeout=3,
                      headers={"X-Service-Key": SERVICE_KEY},
                      json={"items": [{"product_id": d["product_id"], "qty": d["qty"]} for d in detail]})
    if r.status_code != 200:
        return jsonify(error=r.json().get("error", "No fue posible reservar el inventario")), 409
    oid = "PED-" + uuid.uuid4().hex[:8].upper()
    # Pago: en producción se delega a una pasarela SaaS certificada PCI DSS (simulado aquí)
    db = get_db()
    db.execute("INSERT INTO orders(id,user_id,items,total_cop,status,payment_status) VALUES(?,?,?,?,?,?)",
               (oid, g.user["sub"], json.dumps(detail, ensure_ascii=False), total, "CONFIRMADO", "APROBADO (simulado)"))
    db.commit()
    log_event("order_created", order_id=oid, user_id=g.user["sub"], total_cop=total)
    return jsonify(id=oid, items=detail, total_cop=total, status="CONFIRMADO",
                   payment_status="APROBADO (simulado)"), 201


def _row(r):
    d = dict(r)
    d["items"] = json.loads(d["items"])
    return d


@app.get("/api/orders")
@require_auth()
def list_orders():
    db = get_db()
    if g.user["role"] == "admin":
        rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
                          (g.user["sub"],)).fetchall()
    return jsonify([_row(r) for r in rows])


@app.get("/api/orders/<oid>")
@require_auth()
def get_order(oid):
    r = get_db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not r:
        return jsonify(error="Pedido no encontrado"), 404
    if g.user["role"] != "admin" and r["user_id"] != g.user["sub"]:   # control a nivel de objeto
        return jsonify(error="No autorizado: el pedido pertenece a otro usuario"), 403
    return jsonify(_row(r))
