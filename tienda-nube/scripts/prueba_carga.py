"""Prueba de carga: N solicitudes concurrentes al catálogo; mide rendimiento y reparto entre réplicas."""
import sys, time, statistics, collections, requests
from concurrent.futures import ThreadPoolExecutor
N, C = int(sys.argv[1]), int(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else ""
s = requests.Session(); s.verify = "certs/tienda.crt"; s.trust_env = False
adapter = requests.adapters.HTTPAdapter(pool_connections=C, pool_maxsize=C); s.mount("https://", adapter)


def one(_):
    t0 = time.perf_counter()
    try:
        r = s.get("https://localhost:8443/api/products", timeout=15)
        return r.status_code, (time.perf_counter() - t0) * 1000, r.headers.get("X-Instance")
    except Exception:
        return 0, (time.perf_counter() - t0) * 1000, None


t0 = time.perf_counter()
with ThreadPoolExecutor(C) as ex:
    res = list(ex.map(one, range(N)))
dur = time.perf_counter() - t0
lat = sorted(r[1] for r in res)
codes = collections.Counter(r[0] for r in res)
inst = collections.Counter(r[2] for r in res if r[2])
p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]
print(f"PRUEBA DE CARGA {label}: {N} solicitudes, {C} usuarios concurrentes")
print(f"  Duración total        : {dur:.2f} s")
print(f"  Rendimiento           : {N / dur:.1f} solicitudes/s")
print(f"  Latencia p50 / p95    : {p(.5):.0f} ms / {p(.95):.0f} ms")
print(f"  Códigos HTTP          : {dict(codes)}")
print(f"  Errores               : {sum(v for k, v in codes.items() if k != 200)}")
print("  Reparto entre réplicas:")
for k, v in sorted(inst.items()):
    print(f"     {k}: {v} solicitudes ({v / N * 100:.0f} %)")
