FROM ubuntu:16.04

RUN apt-get update && \
    apt-get install -y \
        git \
        liblua5.1-0-dev \
        lua5.1 \
        pkg-config \
        software-properties-common \
        wget
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
        python2.7 \
        python2.7-dev \
        python3.5 \
        python3.5-dev \
        python3.6 \
        python3.6-dev \
        python3.7 \
        python3.7-dev \
        python3.8 \
        python3.8-distutils \
        python3.8-dev

RUN wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
RUN python2.7 /tmp/get-pip.py --disable-pip-version-check --disable-pip-version-check "pip==19.3.1" && \
    mv -v "$(which pip)" "$(which pip)2.7"
RUN python3.5 /tmp/get-pip.py --disable-pip-version-check --disable-pip-version-check "pip==19.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.5"
RUN python3.6 /tmp/get-pip.py --disable-pip-version-check --disable-pip-version-check "pip==19.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.6"
RUN python3.7 /tmp/get-pip.py --disable-pip-version-check --disable-pip-version-check "pip==19.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.7"
RUN python3.8 /tmp/get-pip.py --disable-pip-version-check --disable-pip-version-check "pip==19.3.1" && \
    mv -v "$(which pip)" "$(which pip)3.8"

RUN pip3.7 install tox

WORKDIR /test/pysoa

CMD ["tox"]

ADD . /test/pysoa
