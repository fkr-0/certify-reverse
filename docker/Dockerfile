ARG CADDY_BUILDER_IMAGE=caddy:2.10.0-builder

FROM golang:alpine AS golang_toolchain

FROM ${CADDY_BUILDER_IMAGE}

RUN apk add --no-cache \
  ca-certificates \
  python3 \
  py3-pip

COPY --from=golang_toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"

WORKDIR /opt/certify-reverse
COPY pyproject.toml README.md ./
COPY src ./src
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

COPY boot.sh /usr/local/bin/boot
RUN chmod +x /usr/local/bin/boot

VOLUME ["/data"]

ENTRYPOINT ["/usr/local/bin/boot"]
