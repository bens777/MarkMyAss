FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8765

# Binds to 0.0.0.0 *inside the container only* so docker-compose.yml's
# 127.0.0.1-only port mapping can reach it -- see docker-compose.yml.
# This is not a "public" bind in the way ghostmark ui's default is:
# nothing is reachable unless you change the port mapping yourself.
CMD ["ghostmark", "ui", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
