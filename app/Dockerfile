FROM python:3.13-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 1000 --create-home app \
 && mkdir -p /var/log/app && chown app:app /var/log/app && chmod 755 /var/log/app
WORKDIR /app
COPY server.py .
USER app
ENV PORT=8080 LOG_FILE=/var/log/app/orders-api.log
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=2)"
CMD ["python", "server.py"]
