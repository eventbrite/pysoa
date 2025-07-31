FROM python:3.12-slim

# Install system dependencies (updated for lupa instead of old Lua bindings)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        pkg-config \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Install tox and lupa
RUN pip install --upgrade pip setuptools wheel tox lupa>=2.0

WORKDIR /test/pysoa

ADD . /test/pysoa

CMD ["tox"]
