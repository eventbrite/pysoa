#!/bin/bash

# For running functional tests locally or on Travis using Docker and Docker Compose.
# Requires at least Docker Compose version 1.23.0.

DCF=tests/functional/docker/docker-compose.yaml

export DOCKER_BINARY_BIND_SOURCE=$(which docker)

function cleanup() {
    rm -rf tests/functional/run/.coverage.* tests/functional/run/.coverage tests/functional/run/redis
}
cleanup

if [[ "$1" == "clean" ]]
then
    docker-compose -f $DCF down
    cleanup
    exit 0
fi

verbose="false"
if [[ "$1" == "verbose" ]]
then
    verbose="true"
    shift
fi

set -e

mkdir -p tests/functional/run/redis
for r in 5 6
do
    cp -f "tests/functional/docker/redis/redis${r}-standalone.conf" "tests/functional/run/redis/redis${r}-standalone.conf"
    cp -f "tests/functional/docker/redis/redis${r}-master.conf" "tests/functional/run/redis/redis${r}-master.conf"
    for i in 1 2 3
    do
        cp -f "tests/functional/docker/redis/redis${r}-replica.conf" "tests/functional/run/redis/redis${r}-replica${i}.conf"
        cp -f "tests/functional/docker/redis/sentinel${r}.conf" "tests/functional/run/redis/sentinel${r}-${i}.conf"
    done
    chmod -v 0666 tests/functional/run/redis/*
done

if [[ ! -f tests/functional/run/tls/ca.crt ]] || [[ ! -f tests/functional/run/tls/redis.key ]] || [[ ! -f tests/functional/run/tls/redis.crt ]]
then
    rm -rf tests/functional/run/tls
    mkdir -p tests/functional/run/tls
    openssl genrsa -out tests/functional/run/tls/ca.key 4096
    openssl req \
        -x509 -new -nodes -sha256 \
        -key tests/functional/run/tls/ca.key \
        -days 3650 \
        -subj '/O=Redis Test/CN=Certificate Authority' \
        -out tests/functional/run/tls/ca.crt
    openssl genrsa -out tests/functional/run/tls/redis.key 2048
    openssl req \
        -new -sha256 \
        -key tests/functional/run/tls/redis.key \
        -subj '/O=Redis Test/CN=Server' | \
        openssl x509 \
            -req -sha256 \
            -CA tests/functional/run/tls/ca.crt \
            -CAkey tests/functional/run/tls/ca.key \
            -CAserial tests/functional/run/tls/ca.txt \
            -CAcreateserial \
            -days 365 \
            -out tests/functional/run/tls/redis.crt
fi

set -x

docker build --tag pysoa-test-mysql --file tests/functional/docker/Dockerfile-mysql . &
docker build --tag pysoa-test-service --file tests/functional/docker/Dockerfile-service . &
wait
docker build --tag pysoa-test-service-echo --file tests/functional/services/echo/Dockerfile . &
docker build --tag pysoa-test-service-meta --file tests/functional/services/meta/Dockerfile . &
docker build --tag pysoa-test-service-user --file tests/functional/services/user/Dockerfile . &
docker build --tag pysoa-test-test --file tests/functional/docker/Dockerfile-test . &
wait
docker build --tag pysoa-test-service-echo-double-import-trap \
    --file tests/functional/services/echo/Dockerfile-double-import-trap .

set +ex

docker-compose -f $DCF up -d
RET=$?

if [[ $RET -gt 0 ]]
then
    docker ps|grep pysoa-test
    docker-compose -f $DCF logs
    docker-compose -f $DCF down
    cleanup
    exit $RET
fi

sleep 2

docker ps|grep -E  "redis(4|5)-"
docker ps|grep "pysoa-test"

if [[ "$1" == "up-only" ]]
then
    exit 0
fi

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

cleanup

exit $RET
