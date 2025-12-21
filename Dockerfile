FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync && uv pip install python-dotenv

COPY . .

ENV PYTHONPATH=/app

CMD ["uv", "run", "run.py"]
