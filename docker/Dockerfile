ARG CADDY_BUILDER_IMAGE=caddy:2.10.0-builder

FROM ${CADDY_BUILDER_IMAGE}

RUN apk add --no-cache --upgrade \
  ca-certificates \
  expat \
  python3 \
  py3-pip \
  py3-virtualenv

WORKDIR /opt/certify-reverse
COPY pyproject.toml README.md ./
COPY src ./src
RUN virtualenv --no-download /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

COPY boot.sh /usr/local/bin/boot
RUN chmod +x /usr/local/bin/boot

VOLUME ["/data"]

ENTRYPOINT ["/usr/local/bin/boot"]
