#!/bin/bash

if [[ "$1" != "--no-flake" ]] && [[ "$2" != "--no-flake" ]]
then
    echo "Running Flake8..."
    flake8
    RET=$?
else
    RET=0
fi

echo "Checking for prohibited thread-local usage..."

args=(--include \*.py --exclude compatibility.py --exclude-dir .git --exclude-dir build --exclude-dir .eggs --exclude-dir *.egg-info --exclude-dir .tox)

set -o pipefail
grep -r "${args[@]}" 'threading\.local' . | sed 's/.*/ERROR: Prohibited thread local usage found: &/'
ret_sub=$?
if [[ $ret_sub -eq 0 ]] && [[ $RET -eq 0 ]]
then
    RET=200
fi

for f in $(grep -r -l "${args[@]}" 'from threading' .)
do
    python - <<____HERE
import importlib, threading
m = importlib.import_module('${f}'.strip('.').strip('/').replace('.py', '').replace('/', '.'))
exit(1 if any(v for v in vars(m).values() if v == threading.local) else 0)
____HERE
    ret_sub=$?

    if [[ $ret_sub -gt 0 ]]
    then
        echo "ERROR: Prohibited thread local usage found: ${f}"
        if [[ $RET -eq 0 ]]
        then
            RET=200
        fi
    fi
done

if [[ "$1" != "--no-mypy" ]] && [[ "$2" != "--no-mypy" ]]
then
    echo "Running MyPy..."
    mypy .
    ret_sub=$?
    if [[ $ret_sub -gt 0 ]] && [[ $RET -eq 0 ]]
    then
        RET=$ret_sub
    fi
fi

exit $RET
