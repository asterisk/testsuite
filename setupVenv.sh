#!/usr/bin/env bash
set -e

function do_pip_setup {
	python -m pip install --upgrade pip
	python -m pip install wheel setuptools build
	python -m pip install -r ./requirements.txt
	python -m pip install -r ./extras.txt
	md5sum requirements.txt extras.txt > $1/checksums
}


if [[ "$VIRTUAL_ENV" != "" ]]
then
	echo "Detected activated virtual environment:" $VIRTUAL_ENV
	echo "Skipping creation of new environment, configuring"
	do_pip_setup $VIRTUAL_ENV
else
	python3 -m venv .venv
	source .venv/bin/activate
	echo "Activated virtual environment:" $VIRTUAL_ENV
	if [[ "$VIRTUAL_ENV" != "" ]]
	then
		echo "Configuring virtual environment"
		do_pip_setup $VIRTUAL_ENV
	else
		echo "Virtual environment failed"
	fi
fi

