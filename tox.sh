#!/bin/bash -ex

docker build -t pysoa-test .

if [[ -z "$1" ]]
then
    docker run -it --rm pysoa-test
else
    docker run -it --rm pysoa-test tox "$@"
fi
