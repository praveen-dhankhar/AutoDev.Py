FROM python:3.11-slim

RUN groupadd --gid 1000 sandbox \
    && useradd \
        --uid 1000 \
        --gid 1000 \
        --home-dir /home/sandbox \
        --create-home \
        --shell /usr/sbin/nologin \
        sandbox

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
USER 1000:1000

CMD ["python", "-I", "-B", "-"]
