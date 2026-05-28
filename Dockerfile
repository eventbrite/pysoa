FROM 353605023268.dkr.ecr.us-east-1.amazonaws.com/python3_tox:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    lua5.2 \
    liblua5.2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /pysoa/

COPY . .

CMD ["tox"]
