#!/bin/bash -ex

# For running tests using Tox in a Docker environment

if [[ "$1" == "--reset" ]]
then
    docker image rm pysoa-test
    exit
fi

docker build -t pysoa-test .

if [[ -z "$1" ]]
then
    docker run -it --rm --mount "type=volume,destination=/test/pysoa/.tox" pysoa-test
else
    docker run -it --rm --mount "type=volume,destination=/test/pysoa/.tox" pysoa-test tox "$@"
fi
