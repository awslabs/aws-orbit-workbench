#!/bin/bash

set -x

cat <<EOF |  orbit run notebook --env dev-env --team lake-creator --user testing --wait --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "compute_type": "ecs",
          "node_type": "fargate"
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