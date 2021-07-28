#!/bin/bash

set -x

cat <<EOF |  orbit schedule notebook --env $ENV_NAME --team lake-creator --user testing --wait --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "node_type": "ec2",
          "podsetting":"orbit-runner-support-small"
      },
      "tasks":  [{
          "notebookName": "sanity-good.ipynb",
          "sourcePath": "/home/jovyan/shared/samples/notebooks/Z-Tests",
          "targetPath": "/home/jovyan/shared/regression/notebooks/Z-Tests",
          "params": {
          }
        }]
 }
EOF

echo $?