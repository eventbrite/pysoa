#!/bin/bash

# For running tests locally (not Docker, not Tox) with all dependencies already installed

coverage run --parallel-mode -m pytest tests/unit tests/integration "$@"
RET=$?

coverage combine
ret_sub=$?
if [[ $ret_sub -gt 0 ]] && [[ $RET -eq 0 ]]
then
    RET=$ret_sub
fi

coverage report
ret_sub=$?
if [[ $ret_sub -gt 0 ]] && [[ $RET -eq 0 ]]
then
    RET=$ret_sub
fi

echo "Inspecting code..."
./lint.sh
ret_sub=$?
if [[ $ret_sub -gt 0 ]] && [[ $RET -eq 0 ]]
then
    RET=$ret_sub
fi

exit $RET
