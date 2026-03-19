FROM apify/actor-python:3.11

COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

CMD ["python", "-m", "src.main"]
