#!/bin/bash

set -x

cat <<EOF |  orbit run notebook --env dev-env --team $TEST_TEAM_SPACE --user testing --wait --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "node_type": "ec2"
      },
      "tasks":  [{
          "notebookName": "sanity-good.ipynb",
          "sourcePath": "/efs/shared/samples/notebooks/Z-Tests",
          "targetPath": "/efs/shared/regression/notebooks/Z-Tests",
          "params": {
          }
        }]
 }
EOF

ret=$?
if [ $ret -eq 0 ]
then
    echo "good-sanity-test failed"
else
    echo "good-sanity-test passed"
    exit 255
fi