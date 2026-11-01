"""Límite de solicitudes en /api/users/login: 8 intentos fallidos seguidos desde la misma IP."""
import requests, time
s = requests.Session(); s.verify = "certs/tienda.crt"; s.trust_env = False
print("PRUEBA DE LÍMITE DE INTENTOS DE INICIO DE SESIÓN (rate limiting · 10/min, ráfaga 5)")
for i in range(1, 11):
    r = s.post("https://localhost:8443/api/users/login", json={"email": "cliente.a@correo.co", "password": f"intento{i}"})
    print(f"  intento {i}: HTTP {r.status_code}  {'bloqueado por el API Gateway' if r.status_code == 429 else r.json().get('error')}")
