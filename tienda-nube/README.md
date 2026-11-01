# Tienda Nube · Demo de computación en la nube (Guía 7 · Alternativa B)

Plataforma de comercio electrónico en contenedores: microservicios de usuarios, productos, inventario
y pedidos detrás de un API Gateway (nginx) con HTTPS, límite de solicitudes, balanceo de carga entre
réplicas, monitoreo de salud, registros en JSON y copias de seguridad.

## 1. Requisitos (una sola vez)
1. **Docker Desktop** (Windows o Mac) o Docker Engine + Compose (Linux): https://www.docker.com/products/docker-desktop/
   - En Windows, acepte activar WSL 2 si el instalador lo pide y reinicie.
   - Abra Docker Desktop y espere a que diga *Engine running*.
2. **Python 3.10 o superior** (solo para los scripts de prueba): https://www.python.org/downloads/
   - En Windows marque *Add python.exe to PATH* al instalar.
3. Librería `requests`:
   ```
   pip install requests
   ```

## 2. Levantar la plataforma
Descomprima el .zip, abra una terminal **dentro de la carpeta `tienda-nube`** y ejecute:

```
python scripts/init_secrets.py
docker compose up -d --build
docker compose ps
```
(En Mac/Linux use `python3` en lugar de `python`.)

La primera vez tarda unos minutos porque descarga las imágenes `python:3.12-slim` y `nginx:1.27-alpine`.
Cuando `docker compose ps` muestre los servicios como **healthy**, abra:

**https://localhost:8443**

El navegador advertirá que el certificado no es de confianza (es autofirmado, de laboratorio):
elija *Configuración avanzada → Continuar a localhost*.

Usuarios de prueba (datos ficticios):

| Usuario | Contraseña | Rol |
|---|---|---|
| cliente.a@correo.co | ClienteA#2026 | cliente |
| cliente.b@correo.co | ClienteB#2026 | cliente |
| operador@tienda.co | Operador#2026 | operador |
| admin@tienda.co | Admin#2026 | admin |

## 3. Ejecutar las pruebas (generan las evidencias)
Siempre desde la carpeta `tienda-nube`:

```
python scripts/pruebas_seguridad.py
python scripts/prueba_fuerza_bruta.py

docker compose up -d --scale products=1
docker compose exec gateway nginx -s reload
python scripts/prueba_carga.py 400 20 "(1 réplica)"

docker compose up -d --scale products=3
docker compose exec gateway nginx -s reload
python scripts/prueba_carga.py 400 20 "(3 réplicas)"

python scripts/prueba_falla.py tienda-nube-products-2

docker compose --profile ops run --rm backup backup
docker compose --profile ops run --rm backup restore orders
```

Notas:
- `prueba_fuerza_bruta.py` bloquea el inicio de sesión desde su equipo durante ~1 minuto (es lo que
  demuestra). Si después corre `pruebas_seguridad.py`, espere un minuto antes.
- Otras vistas útiles: `docker compose logs -f gateway`, `docker stats`, y https://localhost:8443/status

## 4. Apagar
```
docker compose down        # detiene y conserva los datos
docker compose down -v     # detiene y borra también las bases de datos
```

## Problemas comunes
| Síntoma | Solución |
|---|---|
| `port is already allocated` (8080 u 8443) | Cierre el programa que usa ese puerto o cambie `"8443:443"` en docker-compose.yml |
| `Cannot connect to the Docker daemon` | Abra Docker Desktop y espere a que el motor arranque |
| `python` no se reconoce | Use `py` (Windows) o `python3` (Mac/Linux) |
| La página no carga justo después de `up` | Espere a que todos los servicios estén *healthy* |
| Error de certificado en los scripts | Ejecute los scripts desde la carpeta `tienda-nube` (leen `certs/tienda.crt`) |

## Estructura
```
services/   common.py (JWT, RBAC, logs, salud), users.py, products.py, inventory.py, orders.py,
            monitor.py, backup.py
gateway/    nginx.conf (TLS, rate limiting, balanceo, reintentos), html/index.html (interfaz web)
scripts/    init_secrets.py y scripts de prueba
evidencias/ salidas y capturas de las pruebas
diagramas/  arquitectura AWS y arquitectura de la demo (HTML y PNG)
```

El pago se simula; en producción se delega a una pasarela certificada PCI DSS. La latencia de 40 ms del
catálogo (`SIMULATED_LATENCY_MS`) representa el acceso a una base de datos administrada remota.
