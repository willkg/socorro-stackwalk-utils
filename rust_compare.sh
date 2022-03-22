#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Pulls down crash data from prod, runs minidump-stackwalk on it, and compares
# the processed crash json_dump data with minidump-stackwalk output.
#
# Requires crashstats-tools:
#
# https://pypi.org/project/crashstats-tools/
#
# Usage: ./rust_compare.sh [CRASHID] [CRASHID...]
#
#    Specify crash ids by command line.
#
# Usage: cat crashids.txt | ./rust_compare.sh
#
#    Pull crash ids from stdin.
#
# Usage: ./rust_compare.shOr
#
#    Run supersearch and use those 20 crashids.
#
# Set CRASHSTATS_API_TOKEN in the environment to the API token you created in
# https://crash-stats.mozilla.org/api/tokens/ that has "View Raw Dumps" and
# "View Personal Identifiable Information" permissions.
#
# You must have access to protected data to use this.

set -e

CACHEDIR="$(pwd)/tmp"
DATADIR="$(pwd)/crashdata"
RUSTDIR="${DATADIR}/rust"
DOPAUSE="1"

mkdir -p "${CACHEDIR}" || true
mkdir -p "${RUSTDIR}" || true

export $(cat .env | grep -v '^# ' | xargs)

if [ "${CRASHSTATS_API_TOKEN}" == "" ]; then
    echo "You need to set the CRASHSTATS_API_TOKEN."
    exit 1;
fi

if [[ $# -eq 0 ]];
then
    if [ -t 0 ];
    then
        # No args and no stdin, so get from supersearch
        echo "Getting 20 crashids from supersearch..."
        CRASHIDS=$(supersearch --product=Firefox --num=20)
    else
        # No args, so get from stdin
        echo "Getting crashids from stdin..."
        set -- ${@:-$(</dev/stdin)}
        CRASHIDS=$@
        DOPAUSE="0"
    fi
else
    # Args
    echo "Getting crashids from args..."
    CRASHIDS=$@
fi

for CRASHID in ${CRASHIDS[@]};
do
    fetch-data --raw --processed --dumps "${DATADIR}" "${CRASHID}"

    minidump-stackwalk \
        --verbose=error \
        --symbols-cache="${CACHEDIR}" \
        --symbols-tmp="${CACHEDIR}" \
        --symbols-url=https://symbols.mozilla.org/ \
        --evil-json="${DATADIR}/raw_crash/${CRASHID}" \
        --json \
        --pretty \
        --output-file="${RUSTDIR}/${CRASHID}.json" \
        "${DATADIR}/upload_file_minidump/${CRASHID}" || true

    # Compare processed crash to minidump stackwalk output
    python dumpdiff.py "${DATADIR}/processed_crash/${CRASHID}" "${RUSTDIR}/${CRASHID}.json" || true
    echo ""
    echo ""
    echo ""
    read val1
done
