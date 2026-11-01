# Imagen de los microservicios (una sola imagen; SERVICE_NAME define cuál se ejecuta)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "flask==3.1.*" "pyjwt==2.*" "bcrypt==4.*" "gunicorn==23.*" "requests==2.*"
WORKDIR /app
COPY services/ /app/
RUN mkdir -p /data && chown nobody:nogroup /data
# Principio de mínimo privilegio: el proceso no se ejecuta como root
USER nobody
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)" || exit 1
CMD python3 -m gunicorn --workers ${WORKERS:-2} --bind 0.0.0.0:5000 --access-logfile - ${SERVICE_NAME}:app
