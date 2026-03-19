FROM apify/actor-python:3.12

COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt && playwright install chromium --with-deps

COPY . .

CMD ["python", "-m", "src.main"]
