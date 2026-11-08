FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-verified.txt /app/requirements.txt
COPY backend/requirements-integration.txt /app/requirements-integration.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-integration.txt
COPY backend /app/backend
COPY data /app/data
COPY scripts /app/scripts
RUN mkdir -p /app/runtime /app/models/checkpoints
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000"]
