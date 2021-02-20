#!/bin/bash

set -x

cat <<EOF |  orbit run notebook --env dev-env --team $TEST_TEAM_SPACE --user testing --wait --debug --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "compute_type": "ecs",
          "node_type": "fargate",
          "add_ebs": "True"
      },
      "tasks":  [{
          "notebookName": "sanity-good.ipynb",
          "sourcePath": "/efs/shared/samples/notebooks/Z-Tests",
          "targetPath": "/efs/shared/regression/notebooks/Z-Tests",
          "params": {
          },
          "ExecutionType": "ecs"
        }]
 }
EOF

echo $?