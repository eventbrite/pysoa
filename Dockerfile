FROM 353605023268.dkr.ecr.us-east-1.amazonaws.com/python3_tox:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    python3.8-dev \
    lua5.2 \
    liblua5.2-dev \
    && rm -rf /var/lib/apt/lists/*

# python3.8-dev installs python3.8.pc into /usr/lib/python3.8/pkgconfig,
# which is not in pkg-config's default search path — mirror what Travis does.
ENV PKG_CONFIG_PATH=/usr/lib/python3.8/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig

WORKDIR /pysoa/

COPY . .

CMD ["tox"]
