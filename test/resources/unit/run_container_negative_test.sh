#!/bin/bash

set -x

cat <<EOF |  orbit run notebook --env dev-env --team $TEST_TEAM_SPACE --user testing --wait --debug --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "node_type": "ec2",
      },
      "tasks":  [{
          "notebookName": "sanity-bad.ipynb",
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
    echo "bad-sanity-test failed"
    exit 255
else
    echo "bad-sanity-test passed"
fi
