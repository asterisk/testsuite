#!/usr/bin/env bash
set -e

REALTIME=false
declare -a VENV_ARGS

for a in "$@" ; do
	if [ "$a" == "--realtime" ] ; then
		REALTIME=true
	else
		VENV_ARGS+=( "$a" )
	fi
done

function do_pip_setup {
	python3 -m pip install --upgrade pip
	python3 -m pip install wheel setuptools build
	python3 -m pip install -r ./requirements.txt
	python3 -m pip install -r ./extras.txt || {
		echo "**************************" >&2
		echo "Some optional python requirements failed to install. The following tests may not run:" >&2
		grep -lEr "python\s*:\s*[']?yappcap" tests >&2
		echo "**************************" >&2
	}
	$REALTIME && python3 -m pip install -r ./requirements-realtime.txt
	md5sum requirements.txt extras.txt requirements-realtime.txt > $1/checksums
}

if [[ "$VIRTUAL_ENV" != "" ]]
then
	echo "Detected activated virtual environment:" $VIRTUAL_ENV
	echo "Skipping creation of new environment, configuring"
	do_pip_setup $VIRTUAL_ENV
else
	python3 -m venv ${VENV_ARGS[@]} .venv
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

