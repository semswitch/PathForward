FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_PROGRESS_BAR=off
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY pathforward ./pathforward
COPY hosted ./hosted
COPY skills ./skills
COPY scripts ./scripts

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir --progress-bar off -r hosted/pathforward_orchestrator/requirements.txt

EXPOSE 8088
CMD ["python", "-m", "hosted.pathforward_orchestrator.main"]
