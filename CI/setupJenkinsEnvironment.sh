#!/usr/bin/env bash
CIDIR=$(dirname $(readlink -fn $0))
source $CIDIR/ci.functions

mkdir -p /srv/cache/externals /srv/cache/sounds /srv/cache/ccache || :
chown -R jenkins:users /srv/cache
chmod g+rw /srv/cache/ccache
chmod g+s /srv/cache/ccache
if [ -n "${OUTPUT_DIR}" ] ; then
	mkdir -p "${OUTPUT_DIR}" || :
	chown -R jenkins:users "${OUTPUT_DIR}"
fi
