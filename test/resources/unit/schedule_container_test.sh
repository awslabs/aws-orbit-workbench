#!/bin/bash

set -x

cat <<EOF |  orbit schedule notebook --env $ENV_NAME --team lake-creator --user testing --wait --tail-logs -
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

echo $?