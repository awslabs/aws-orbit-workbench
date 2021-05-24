#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

cd $DIR/../plugins

for dir in `ls`
do
  echo $dir
  cd $dir
  rm -fr build
  ./fix.sh &&./validate.sh
  cd ..
done