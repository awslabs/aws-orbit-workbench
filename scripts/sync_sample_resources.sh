#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars


toolkit=$(orbit list env --variable=toolkitbucket)
echo "Toolkit bucket: $toolkit"
echo "s3 sync $SAMPLES_DIR s3://$toolkit/samples"
aws s3 sync $SAMPLES_DIR s3://$toolkit/samples