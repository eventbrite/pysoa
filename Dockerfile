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
		python3.7-dev
RUN wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py && \
	python3.7 /tmp/get-pip.py && \
	pip install tox

WORKDIR /test/pysoa

CMD ["tox"]

ADD . /test/pysoa
