FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY content ./content

RUN pip install --no-cache-dir .

# Drop root
RUN useradd --create-home --shell /usr/sbin/nologin unubot
USER unubot

CMD ["python", "-m", "unubot"]
