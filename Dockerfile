FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

ADD . /app

WORKDIR /app
RUN uv sync --frozen

CMD [".venv/bin/python", "src/csm_bot/main.py"]
