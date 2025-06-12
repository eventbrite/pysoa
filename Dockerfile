FROM ubuntu:22.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        git \
        liblua5.1-0-dev \
        lua5.1 \
        pkg-config \
        software-properties-common \
        wget
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
        python3.8 \
        python3.8-dev \
        python3.8-distutils \
        python3.9 \
        python3.9-dev \
        python3.9-distutils \
        python3.10 \
        python3.10-dev \
        python3.10-distutils \
        python3.11 \
        python3.11-dev \
        python3.11-distutils \
        python3.12 \
        python3.12-dev \
        python3.12-distutils

RUN wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
RUN python3.8 /tmp/get-pip.py --disable-pip-version-check "pip==23.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.8"
RUN python3.9 /tmp/get-pip.py --disable-pip-version-check "pip==23.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.9"
RUN python3.10 /tmp/get-pip.py --disable-pip-version-check "pip==23.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.10"
RUN python3.11 /tmp/get-pip.py --disable-pip-version-check "pip==23.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.11"
RUN python3.12 /tmp/get-pip.py --disable-pip-version-check "pip==23.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.12"

RUN pip3.12 install tox

WORKDIR /test/pysoa

CMD ["tox"]

ADD . /test/pysoa
