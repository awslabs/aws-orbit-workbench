#!/bin/bash

set -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

$DIR/../scripts/update_repo.sh cli aws-orbit

rm -rf dist
