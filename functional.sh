#!/bin/bash

# For running functional tests locally or on Travis using Docker and Docker Compose.
# Requires at least Docker Compose version 1.23.0.

DCF=tests/functional/docker/docker-compose.yaml

rm -f tests/functional/run/.coverage.* tests/functional/run/.coverage

if [[ "$1" == "clean" ]]
then
    docker-compose -f $DCF down
    exit 0
fi

verbose="false"
if [[ "$1" == "verbose" ]]
then
    verbose="true"
    shift
fi

set -ex

docker build --tag pysoa-test-mysql --file tests/functional/docker/Dockerfile-mysql .
docker build --tag pysoa-test-redis --file tests/functional/docker/Dockerfile-redis .
docker build --tag pysoa-test-redis-sentinel --file tests/functional/docker/Dockerfile-redis-sentinel .
docker build --tag pysoa-test-service --file tests/functional/docker/Dockerfile-service .
docker build --tag pysoa-test-service-echo --file tests/functional/services/echo/Dockerfile .
docker build --tag pysoa-test-service-meta --file tests/functional/services/meta/Dockerfile .
docker build --tag pysoa-test-service-user --file tests/functional/services/user/Dockerfile .
docker build --tag pysoa-test-test --file tests/functional/docker/Dockerfile-test .

set +ex

export DOCKER_BINARY_BIND_SOURCE=$(which docker)

docker-compose -f $DCF up -d
RET=$?

if [[ $RET -gt 0 ]]
then
    docker ps|grep pysoa-test
    docker-compose -f $DCF logs
    docker-compose -f $DCF down
    rm tests/functional/run/.coverage.*
    exit $RET
fi

docker ps|grep pysoa-test

echo  "Running functional tests..."
#docker-compose -f $DCF exec -T test pytest tests/functional
docker-compose -f $DCF exec -T test \
    coverage run --concurrency=multiprocessing --rcfile=/srv/run/.coveragerc -m \
    pytest -vv -p no:pysoa_test_plan tests/functional "$@"
RET=$?

# Stop these now, so that coverage files get written
docker-compose -f $DCF stop user_service meta_service echo_service

echo "The following coverage files were created (should be 18+ files, something might be wrong otherwise):"
( cd tests/functional/run/; ls .coverage.* 2>/dev/null || echo "(none)" )

echo "Combining coverage files..."
docker-compose -f $DCF exec -T --workdir /srv/run/ test coverage combine
ret_sub=$?
if [[ $ret_sub -gt 0 ]] && [[ $RET -eq 0 ]]
then
    echo "ERROR: Combining coverage failed with error code: $ret_sub"
    RET=$ret_sub
fi

echo "Calculating coverage..."
docker-compose -f $DCF exec -T --workdir /srv/run/ test coverage report
ret_sub=$?
if [[ $ret_sub -gt 0 ]]
then
    if [[ $ret_sub -eq 2 ]]
    then
        echo "ERROR: Coverage report failed because the minimum coverage threshold was not met."
    else
        echo "ERROR: Coverage report generation failed with exit code: $ret_sub"
    fi
    if [[ $RET -eq 0 ]]
    then
        RET=$ret_sub
    fi
fi

docker-compose -f $DCF stop

if [[ "$verbose" == "true" ]]
then
    docker-compose -f $DCF logs
fi

docker-compose -f $DCF down

unset DOCKER_BINARY_BIND_SOURCE

exit $RET
