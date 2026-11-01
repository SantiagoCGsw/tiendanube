"""Genera los secretos y el certificado TLS de laboratorio (Windows, Mac o Linux).
Uso (desde la carpeta del proyecto):  python scripts/init_secrets.py
"""
import os, secrets, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
for d in ("secrets", "certs", "backups"):
    os.makedirs(d, exist_ok=True)


def write(path, value):
    if not os.path.exists(path):
        with open(path, "w", newline="\n") as f:
            f.write(value + "\n")
        print("  creado", path)


write("secrets/jwt_secret.txt", secrets.token_hex(32))
write("secrets/service_key.txt", secrets.token_hex(24))
write("secrets/admin_password.txt", "Admin#2026")

if os.path.exists("certs/tienda.crt") and os.path.exists("certs/tienda.key"):
    print("Certificado ya existe.")
    sys.exit(0)

args = ["req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "365",
        "-subj", "/C=CO/O=Tienda Nube/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"]
if shutil.which("openssl"):                       # Linux, Mac o Git Bash
    subprocess.run(["openssl", *args, "-keyout", "certs/tienda.key", "-out", "certs/tienda.crt"],
                   check=True, capture_output=True)
else:                                             # Windows sin openssl: se usa un contenedor
    certs = os.path.abspath("certs")
    subprocess.run(["docker", "run", "--rm", "-v", f"{certs}:/certs", "nginx:1.27-alpine", "sh", "-c",
                    "apk add --no-cache openssl >/dev/null && openssl " + " ".join(
                        f'"{a}"' if " " in a else a for a in args) +
                    " -keyout /certs/tienda.key -out /certs/tienda.crt 2>/dev/null && chmod 644 /certs/*"],
                   check=True)
for f in ("certs/tienda.key", "secrets/jwt_secret.txt", "secrets/service_key.txt", "secrets/admin_password.txt"):
    try:
        os.chmod(f, 0o644)                        # el contenedor corre como usuario sin privilegios
    except OSError:
        pass
print("Secretos y certificado listos.")
