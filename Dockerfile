FROM caddy:2.10.0-builder

RUN apk add --no-cache \
  dnsmasq \
  openssh-client rsync \
  curl jq git \
  python3 py3-pip py3-yaml py3-rich \
  logrotate tzdata \
  su-exec libcap openssl

COPY boot.sh /usr/bin/boot
COPY app.py /usr/bin/app
COPY templates.py /usr/bin/templates.py
COPY status.py /usr/bin/status.py
COPY config.yml /config.yml

RUN chmod +x /usr/bin/boot /usr/bin/app

VOLUME ["/data"]

ENTRYPOINT ["/usr/bin/boot"]
