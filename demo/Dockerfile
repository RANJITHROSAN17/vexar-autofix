FROM python:3.11-slim

# git is required because the scanner is installed from a pinned commit SHA rather than a
# registry. That pin is deliberate: judges must reproduce the same verification behaviour.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples

RUN pip install --no-cache-dir -e ".[demo]"

COPY demo ./demo

ENV PYTHONUNBUFFERED=1 \
    PORT=7860

EXPOSE 7860

# Spaces expects the app on 7860 by default; bind 0.0.0.0 so the proxy can reach it.
CMD ["uvicorn", "demo.app:app", "--host", "0.0.0.0", "--port", "7860"]
