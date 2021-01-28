#!/bin/bash

set -ex

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

$DIR/set_jupyter_user_pip_conf.sh
$DIR/update_repo.sh cli aws-orbit
$DIR/update_repo.sh sdk aws-orbit-sdk
