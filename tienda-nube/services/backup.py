"""Copia de seguridad y restauración de las bases de datos de cada servicio (API de backup de SQLite)."""
import os, sqlite3, sys, time, glob, hashlib

DBS = ["users", "products", "inventory", "orders"]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def backup():
    dest = f"/backups/{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(dest, exist_ok=True)
    for name in DBS:
        src = sqlite3.connect(f"/data/{name}/db.sqlite3")
        dst = sqlite3.connect(f"{dest}/{name}.sqlite3")
        src.backup(dst)           # copia consistente aunque el servicio esté escribiendo
        rows = dst.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        counts = {t[0]: dst.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0] for t in rows
                  if not t[0].startswith("sqlite_")}
        dst.close(); src.close()
        print(f"[BACKUP] {name:<10} -> {dest}/{name}.sqlite3  registros={counts}  sha256={sha(f'{dest}/{name}.sqlite3')}")
    print(f"[BACKUP] Completado: {dest}")


def restore(name):
    latest = sorted(glob.glob("/backups/*/"))[-1]
    src = sqlite3.connect(f"{latest}{name}.sqlite3")
    dst = sqlite3.connect(f"/data/{name}/db.sqlite3")
    src.backup(dst)
    n = {t[0]: dst.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
         for t in dst.execute("SELECT name FROM sqlite_master WHERE type='table'") if not t[0].startswith("sqlite_")}
    src.close(); dst.close()
    print(f"[RESTORE] {name} restaurado desde {latest}  registros={n}")


if __name__ == "__main__":
    backup() if sys.argv[1] == "backup" else restore(sys.argv[2])
