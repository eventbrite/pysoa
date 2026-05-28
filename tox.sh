#!/bin/bash -ex

# For running tests using Tox in a Docker environment with Docker Compose

if [[ "$1" == "--reset" ]]
then
    docker-compose down --rmi all --volumes
    exit
fi

docker-compose build

CONTAINER_NAME="pysoa-tox-run"

docker rm "$CONTAINER_NAME" 2>/dev/null || true

set +e
if [[ -z "$1" ]]
then
    docker-compose run --name "$CONTAINER_NAME" tox
else
    docker-compose run --name "$CONTAINER_NAME" tox tox "$@"
fi
EXIT_CODE=$?
set -e

docker cp "$CONTAINER_NAME":/pysoa/coverage.xml ./coverage.xml 2>/dev/null || true
docker cp "$CONTAINER_NAME":/pysoa/test-results ./test-results 2>/dev/null || true

docker rm "$CONTAINER_NAME" 2>/dev/null || true

exit $EXIT_CODE
