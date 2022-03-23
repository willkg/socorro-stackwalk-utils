#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Download processed crash data from stage and prod and compare the json_dump
# portion of that crash data.
#
# Takes a crashid file which contains crash ids one-per-line. It can handle
# comments that start with a # at the start of the line.
#
# Set CRASHSTATS_API_TOKEN in the environment to the API token you created in
# https://crash-stats.mozilla.org/api/tokens/ that has "View Raw Dumps" and
# "View Personal Identifiable Information" permissions.
#
# Set STAGE_CRASHSTATS_API_TOKEN in the environment to the API token you
# created in https://crash-stats.allizom.org/api/tokens/ (stage server) that
# has "View Raw Dumps" and "View Personal Identifiable Information"
# permissions.
#
# You can set CRASHSTATS_API_TOKEN and STAGE_CRASHSTATS_API_TOKEN as
# environment variables or in a .env file.

# Usage: compare_stage_and_prod.sh CRASHIDFILE

# Load the .env file
export $(cat .env | grep -v '^# ' | xargs)

if [ "${CRASHSTATS_API_TOKEN}" == "" ]; then
    echo "You need to set CRASHSTATS_API_TOKEN. Exiting."
    exit 1;
fi

if [ "${STAGE_CRASHSTATS_API_TOKEN}" == "" ]; then
    echo "You need to set STAGE_CRASHSTATS_API_TOKEN. Exiting."
    exit 1;
fi

mkdir crashdata_stage || true
mkdir crashdata_prod || true

# Load everything from the file mentioned skipping lines that are commented out
FILES=()
while IFS= read -r CRASHID; do
    # skip commented out lines
    if [[ $CRASHID =~ ^#.* ]]
    then
        echo "Skipping..."
        continue
    fi

    FILES+=(${CRASHID})
done < $1

# Iterate through crashids in the file
for CRASHID in ${FILES[@]}; do
    echo ">>> ${CRASHID}"

    # Fetch minidump data from prod
    fetch-data \
        --no-raw --no-dumps --processed \
        crashdata_prod "${CRASHID}"

    # Fetch minidump data from stage
    CRASHSTATS_API_TOKEN="${STAGE_CRASHSTATS_API_TOKEN}" fetch-data \
        --host=https://crash-stats.allizom.org --no-raw --no-dumps --processed \
        crashdata_stage "${CRASHID}"
    
    echo "stage: https://crash-stats.allizom.org/report/index/${CRASHID}  | prod: https://crash-stats.mozilla.org/report/index/${CRASHID}"
    python dumpdiff.py "crashdata_stage/processed_crash/${CRASHID}" "crashdata_prod/processed_crash/${CRASHID}"
    echo ""
    read var1
done
