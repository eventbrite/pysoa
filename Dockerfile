FROM python:3.12-slim

# Install system dependencies (as in the previous Dockerfile)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        liblua5.1-0-dev \
        lua5.1 \
        pkg-config \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Install tox
RUN pip install --upgrade pip setuptools wheel tox

WORKDIR /test/pysoa

ADD . /test/pysoa

CMD ["tox"]
