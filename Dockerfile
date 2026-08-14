# ExifTool and c2patool are installed as separate, independently-licensed
# external binaries -- MarkMyAss never vendors either's source or binary
# in this repository or in the Python package; it only shells out to
# whatever it finds on PATH at runtime. See THIRD_PARTY_LICENSES.md.
#
# c2patool (Apache-2.0/MIT) is published on crates.io, not as a
# conveniently apt-installable Debian package, so it's built from the
# official source in a throwaway Rust build stage and only the resulting
# binary is copied into the final image -- the Rust toolchain itself
# never ships in the image MarkMyAss actually runs.
FROM rust:1-slim-bookworm AS c2patool-builder
# c2patool depends on openssl-sys with the "vendored" feature, which always
# compiles its own OpenSSL from source (system libssl-dev is not enough).
# That vendored build's Configure script needs Perl core modules (e.g.
# FindBin) that the slim image's minimal perl-base doesn't include, so pull
# in the full perl package plus a C toolchain before building.
RUN apt-get update \
    && apt-get install -y --no-install-recommends perl make gcc \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install c2patool

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=c2patool-builder /usr/local/cargo/bin/c2patool /usr/local/bin/c2patool

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

# Run as a non-root user at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin ghostmark \
    && chown -R ghostmark:ghostmark /app
# Dedicated writable mount point for the durable usage-stats SQLite DB.
# Created owned by the non-root user so that a freshly-initialized Docker
# named volume mounted here (see docker-compose.prod.yml) inherits that
# ownership and is writable even with read_only: true on the root fs.
# This holds ONLY aggregate counts -- never any uploaded file.
RUN mkdir -p /data && chown ghostmark:ghostmark /data
USER ghostmark

EXPOSE 8765

# Binds to 0.0.0.0 *inside the container only* so the compose file's
# 127.0.0.1-only port mapping (or a reverse proxy on the host) can reach
# it -- see docker-compose.yml / docker-compose.prod.yml. This is not a
# "public" bind in the way ghostmark ui's own default is: nothing is
# reachable from outside the container unless the port mapping says so.
CMD ["ghostmark", "ui", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
