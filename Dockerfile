FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/models

# Dependencies first, so editing code does not reinstall them.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY . .

# Default: run the tests. Override the command to run anything else.
CMD ["python", "-m", "pytest", "-q"]
