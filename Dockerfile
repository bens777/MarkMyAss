# ExifTool is installed via the OS package manager (Debian/apt) -- GhostMark
# never vendors ExifTool's GPL-licensed source or binary in this repository
# or in the Python package; it only shells out to whatever `exiftool` is on
# PATH at runtime. See THIRD_PARTY_LICENSES.md.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

# Run as a non-root user at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin ghostmark \
    && chown -R ghostmark:ghostmark /app
USER ghostmark

EXPOSE 8765

# Binds to 0.0.0.0 *inside the container only* so the compose file's
# 127.0.0.1-only port mapping (or a reverse proxy on the host) can reach
# it -- see docker-compose.yml / docker-compose.prod.yml. This is not a
# "public" bind in the way ghostmark ui's own default is: nothing is
# reachable from outside the container unless the port mapping says so.
CMD ["ghostmark", "ui", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
