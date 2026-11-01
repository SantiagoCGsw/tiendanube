"""Monitor: descubre las réplicas de cada servicio (DNS de Docker) y consulta su /health."""
import socket, time
import requests
from flask import Flask, jsonify

app = Flask("monitor")
app.json.ensure_ascii = False
SERVICES = ["users", "products", "inventory", "orders"]


@app.get("/status")
def status():
    out, all_up = {}, True
    for s in SERVICES:
        try:
            ips = sorted({a[4][0] for a in socket.getaddrinfo(s, 5000, proto=socket.IPPROTO_TCP)})
        except socket.gaierror:
            ips = []
        reps = []
        for ip in ips:
            t0 = time.perf_counter()
            try:
                r = requests.get(f"http://{ip}:5000/health", timeout=2).json()
                reps.append({"instance": r["instance"], "status": r["status"],
                             "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
            except Exception:
                reps.append({"ip": ip, "status": "DOWN"})
                all_up = False
        if not reps:
            all_up = False
        out[s] = {"replicas": len(reps), "up": sum(r["status"] == "UP" for r in reps), "detail": reps}
    return jsonify(platform="UP" if all_up else "DEGRADED", checked_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                   services=out)
