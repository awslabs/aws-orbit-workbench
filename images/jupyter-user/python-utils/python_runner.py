#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import logging
import os
import sys
from importlib import import_module
from multiprocessing import Pool

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# Hack to make YAML loader not auto-convert datetimes
# https://stackoverflow.com/a/52312810
NoDatesSafeLoader = yaml.SafeLoader
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
    for k, v in NoDatesSafeLoader.yaml_implicit_resolvers.items()
}


def run():
    tasks = yaml.safe_load(os.environ["tasks"])
    compute = yaml.safe_load(os.environ["compute"])

    errors = []
    try:
        errors = runTasks(tasks["tasks"], compute)

    finally:
        if len(errors) > 0:
            logger.error("Execution had errors : %s", errors)
            raise Exception("Execution had errors : " + str(errors))

    return "done python execution"


def runTasks(tasks, compute):
    errors = []
    if "container" in compute["compute"].keys() and "p_concurrent" in compute["compute"]["container"]:
        workers = int(compute["compute"]["container"]["p_concurrent"])
    else:
        workers = 1

    if workers == 1:
        logger.info("Starting tasks execution")
        for task in tasks:
            taskErrors = runTask(task)
            errors.extend(taskErrors)
    else:
        logger.info("Starting tasks execution with %s processes ", workers)
        pool = Pool(processes=workers)

        for taskErrors in pool.map(runTask, tasks):
            if len(taskErrors) > 0:
                errors.extend(taskErrors)

        logger.info("Completed all notebook executions")
        logger.info("current working dir %s", os.getcwd())

    return errors


def runTask(task):
    parameters = task["params"]
    module = task["module"]
    functionName = task["functionName"]
    sourcePaths = task["sourcePaths"]
    for p in sourcePaths:
        sys.path.insert(0, os.path.abspath(p))

    logger.info("import paths: %s", str(sys.path))

    mod = import_module(module)
    func = getattr(mod, functionName)

    errors = []
    try:
        logger.info("Starting task execution for %s.%s", module, functionName)
        func(parameters)
    except Exception as e:
        logger.error("Error during task execution for %s.%s: error %s", module, functionName, e)
        errors.append(e)

    logger.info("Completed task execution for %s.%s", module, functionName)
    return errors
