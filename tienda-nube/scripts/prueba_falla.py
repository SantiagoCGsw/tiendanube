"""Tolerancia a fallos: tráfico continuo mientras se 'cae' una réplica de productos."""
import subprocess, sys, threading, time, collections, requests
s = requests.Session(); s.verify = "certs/tienda.crt"; s.trust_env = False
victim = sys.argv[1]
stop, res, timeline = False, [], []


def worker():
    while not stop:
        t = time.time()
        try:
            r = s.get("https://localhost:8443/api/products", timeout=10)
            res.append((t, r.status_code, r.headers.get("X-Instance")))
        except Exception:
            res.append((t, 0, None))


ths = [threading.Thread(target=worker) for _ in range(6)]
[t.start() for t in ths]
start = time.time()
time.sleep(4)
print(f"[t={time.time()-start:4.1f}s] Se simula la caída del proceso en la réplica {victim}")
subprocess.run(["docker", "exec", victim, "sh", "-c", "kill -9 $(cut -d' ' -f1 /proc/1/task/1/children)"], capture_output=True)
for i in range(16):
    time.sleep(1)
    st = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}} reinicios={{.RestartCount}} salud={{if .State.Health}}{{.State.Health.Status}}{{end}}", victim],
                        capture_output=True, text=True).stdout.strip()
    timeline.append(f"[t={time.time()-start:4.1f}s] Estado de {victim}: {st}")
stop = True
[t.join() for t in ths]
print("\n".join(timeline[::3] + [timeline[-1]]))
codes = collections.Counter(c for _, c, _ in res)
print(f"\nSolicitudes atendidas durante la prueba: {len(res)}")
print(f"Códigos HTTP: {dict(codes)}  ·  disponibilidad observada: {codes.get(200,0)/len(res)*100:.2f} %")
