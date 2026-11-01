"""Pruebas de autenticación, autorización y protección de la información (Etapa 5)."""
import warnings; warnings.filterwarnings("ignore")
import socket, ssl, sys, requests, urllib3
BASE = "https://localhost:8443"
CA = "certs/tienda.crt"
s = requests.Session(); s.verify = CA; s.trust_env = False
results = []


def check(n, desc, resp_status, expected):
    ok = resp_status == expected
    results.append(ok)
    print(f"{n:>2}  {desc:<62} esperado={expected:<4} obtenido={resp_status:<4} {'OK' if ok else 'FALLA'}")


def login(email, pw):
    r = s.post(f"{BASE}/api/users/login", json={"email": email, "password": pw})
    return r, (r.json().get("access_token") if r.status_code == 200 else None)


H = lambda t: {"Authorization": f"Bearer {t}"}
print("=" * 102)
print("PRUEBAS DE ACCESO, AUTENTICACIÓN Y PROTECCIÓN · https://localhost:8443")
print("=" * 102)
check(1, "Consultar pedidos sin token", s.get(f"{BASE}/api/orders").status_code, 401)
check(2, "Consultar pedidos con token falsificado", s.get(f"{BASE}/api/orders", headers=H("abc.def.ghi")).status_code, 401)
r, _ = login("cliente.a@correo.co", "clave-incorrecta")
check(3, "Login de Cliente A con contraseña incorrecta", r.status_code, 401)
r, ta = login("cliente.a@correo.co", "ClienteA#2026")
check(4, "Login de Cliente A con credenciales válidas (emite JWT)", r.status_code, 200)
r = s.post(f"{BASE}/api/orders", headers=H(ta), json={"items": [{"product_id": 3, "qty": 2}, {"product_id": 5, "qty": 1}]})
oid = r.json().get("id")
check(5, f"Cliente A crea un pedido ({oid})", r.status_code, 201)
check(6, "Cliente A consulta su propio pedido", s.get(f"{BASE}/api/orders/{oid}", headers=H(ta)).status_code, 200)
_, tb = login("cliente.b@correo.co", "ClienteB#2026")
check(7, "Cliente B intenta consultar el pedido de Cliente A", s.get(f"{BASE}/api/orders/{oid}", headers=H(tb)).status_code, 403)
check(8, "Cliente A intenta modificar el inventario", s.put(f"{BASE}/api/inventory/1", headers=H(ta), json={"quantity": 999}).status_code, 403)
_, to = login("operador@tienda.co", "Operador#2026")
check(9, "Operador actualiza el inventario del producto 1", s.put(f"{BASE}/api/inventory/1", headers=H(to), json={"quantity": 48}).status_code, 200)
check(10, "Operador intenta crear un pedido (rol no permitido)", s.post(f"{BASE}/api/orders", headers=H(to), json={"items": [{"product_id": 1, "qty": 1}]}).status_code, 403)
_, tadm = login("admin@tienda.co", open("secrets/admin_password.txt").read().strip())
check(11, "Administrador lista todos los usuarios", s.get(f"{BASE}/api/users", headers=H(tadm)).status_code, 200)
check(12, "Cliente A intenta listar todos los usuarios", s.get(f"{BASE}/api/users", headers=H(ta)).status_code, 403)
check(13, "Acceso externo a endpoint interno /internal/inventory/reserve", s.post(f"{BASE}/internal/inventory/reserve", json={}).status_code, 403)
r = s.post(f"{BASE}/api/orders", headers=H(ta), json={"items": [{"product_id": 6, "qty": 50}]})
check(14, "Pedido que supera las existencias (no se descuenta stock)", r.status_code, 409)
r = s.get("http://localhost:8080/api/products", allow_redirects=False)
check(15, "Solicitud por HTTP sin cifrar (redirección a HTTPS)", r.status_code, 301)

print("-" * 102)
print("CIFRADO EN TRÁNSITO (TLS)")
for ver, name in [(ssl.TLSVersion.TLSv1_1, "TLS 1.1"), (ssl.TLSVersion.TLSv1_2, "TLS 1.2"), (ssl.TLSVersion.TLSv1_3, "TLS 1.3")]:
    ctx = ssl.create_default_context(cafile=CA); ctx.minimum_version = ctx.maximum_version = ver
    if ver == ssl.TLSVersion.TLSv1_1:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    try:
        with socket.create_connection(("localhost", 8443), timeout=3) as sock, ctx.wrap_socket(sock, server_hostname="localhost") as tls:
            print(f"    {name}: ACEPTADO  ({tls.cipher()[0]})")
    except Exception as e:
        print(f"    {name}: RECHAZADO ({type(e).__name__})")
h = s.get(f"{BASE}/api/products").headers
print("CABECERAS DE SEGURIDAD")
for k in ["Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options"]:
    print(f"    {k}: {h.get(k)}")
print("=" * 102)
print(f"RESULTADO: {sum(results)}/{len(results)} casos cumplen el resultado esperado")
