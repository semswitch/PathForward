FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY pathforward ./pathforward
COPY hosted ./hosted
COPY skills ./skills
COPY scripts ./scripts

RUN pip install --no-cache-dir -r hosted/pathforward_orchestrator/requirements.txt

EXPOSE 8088
CMD ["python", "-m", "hosted.pathforward_orchestrator.main"]
