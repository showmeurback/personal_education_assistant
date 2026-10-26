# По умолчанию используется зеркало Docker Hub (как в исходном проекте); другое зеркало:
#   docker compose build --build-arg PYTHON_IMAGE=python:3.11-slim
ARG PYTHON_IMAGE=dockerhub.timeweb.cloud/library/python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8000
ENTRYPOINT ["python", "src/main.py"]
