#!/usr/bin/env bash
REINSTALL=0
set -e

if [[ "$VIRTUAL_ENV" != "" ]] ; then
    echo "Currently running inside a python virtual environment, exiting."
    exit 1
fi

if [ -f .venv/checksums ] ; then
	md5sum --status -c .venv/checksums || REINSTALL=1
else
	REINSTALL=1
fi

if [ $REINSTALL -eq 1 ] ; then
    echo "Reinstall required, removing and recreating venv"
	rm -rf .venv
    ./setupVenv.sh > /dev/null 2>&1

fi

source .venv/bin/activate
exec $@

