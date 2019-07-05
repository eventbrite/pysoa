#!/bin/bash -ex

# For running tests locally (not Docker, not Tox) with all dependencies already installed

pytest --cov=pysoa --cov-branch --cov-report=term-missing --cov-fail-under=85
