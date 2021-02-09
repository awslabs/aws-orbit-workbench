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

import json
import logging
import os
import shutil
import time
from multiprocessing import Pool
from typing import List

import papermill as pm
import yaml as yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# Hack to make YAML loader not auto-convert datetimes
# https://stackoverflow.com/a/52312810
NoDatesSafeLoader = yaml.SafeLoader
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
    for k, v in NoDatesSafeLoader.yaml_implicit_resolvers.items()
}


def read_yaml_file(path):
    with open(path, "r") as f:
        return yaml.load(f, Loader=NoDatesSafeLoader)


def run():

    default_output_directory = os.environ.get("output", "private/outputs")

    notebooks = yaml.load(os.environ["tasks"], Loader=NoDatesSafeLoader)
    compute = yaml.load(os.environ["compute"], Loader=NoDatesSafeLoader)

    notebooksToRun = prepareAndValidateNotebooks(default_output_directory, notebooks)
    errors = []
    try:
        errors = runNotebooks(notebooksToRun, compute)
    finally:
        if len(errors) > 0:
            logger.error("Execution had errors : %s", errors)
            raise Exception("Execution had errors : " + str(errors))
        else:
            return "done notebook execution"


def runNotebooks(reportsToRun, compute):
    errors = []
    if "container" in compute["compute"].keys() and "p_concurrent" in compute["compute"]["container"]:
        workers = int(compute["compute"]["container"]["p_concurrent"])
    else:
        workers = 1

    if workers == 1:
        logger.info("Starting tasks execution")
        for task in reportsToRun:
            taskErrors = runNotebook(task)
            errors.extend(taskErrors)
    else:
        logger.info("Starting tasks execution with %s processes ", workers)
        pool = Pool(processes=workers)

        for taskErrors in pool.map(runNotebook, reportsToRun):
            if len(taskErrors) > 0:
                errors.extend(taskErrors)

    logger.info("Completed all notebook executions")

    return errors


def runNotebook(parameters):
    errors = []
    output_path = parameters.get("PAPERMILL_OUTPUT_PATH")
    os_user = parameters.get("JUPYTER_USER_NAME", "jovyan")
    os_group = parameters.get("JUPYTER_USER_GROUP", "users")
    try:
        logger.info("Starting notebook execution for %s", output_path)
        pm.execute_notebook(
            input_path=parameters["PAPERMILL_INPUT_PATH"],
            output_path=output_path,
            parameters=parameters,
            cwd=parameters["PAPERMILL_WORK_DIR"],
            log_output=True,
        )
    except Exception as e:
        logger.error("Error during notebook execution: %s", e)
        pathToOutputNotebookError = os.path.join(
            parameters["PAPERMILL_OUTPUT_DIR_PATH"], "error@" + parameters["PAPERMILL_WORKBOOK_NAME"]
        )

        logger.error("marking error notebook with error %s->%s", output_path, pathToOutputNotebookError)
        errors.append(e)
        if output_path.startswith("s3:"):
            c = "aws s3 mv {} {}".format(output_path, pathToOutputNotebookError)
            print(c)
            os.system(c)
        else:
            logger.error(f"rename {output_path} to {pathToOutputNotebookError}")
            os.rename(output_path, pathToOutputNotebookError)
            output_path = pathToOutputNotebookError

    if not output_path.startswith("s3:"):
        logger.info(f"Changing ownership of output file:  `chown {os_user}:{os_group} {output_path}`")
        shutil.chown(output_path, os_user, os_group)
        os.chmod(output_path, 0o664)

    logger.info("Completed notebook execution: %s", output_path)
    return errors


def prepareAndValidateNotebooks(default_output_directory, notebooks):
    reportsToRun = []
    id = 1
    for notebook in notebooks["tasks"]:
        key = "e{}".format(str(id))
        id += 1
        reportToRun = prepareNotebook(default_output_directory, notebook, key)
        reportsToRun.append(reportToRun)
    return reportsToRun


def print_dir(dir: str, exclude: List[str] = []) -> None:
    logger.debug("Tree structure of %s", dir)
    for root, dirnames, filenames in os.walk(dir):
        if exclude:
            for d in list(dirnames):
                if d in exclude:
                    dirnames.remove(d)
        # print path to all subdirectories first.
        for subdirname in dirnames:
            logger.info(os.path.join(root, subdirname))
        # print path to all filenames.
        for filename in filenames:
            logger.info((os.path.join(root, filename)))


def prepareNotebook(default_output_directory, notebook, key):
    notebookName = notebook["notebookName"]
    sourcePath = notebook["sourcePath"]
    targetPath = notebook.get("targetPath", default_output_directory)
    targetPrefix = notebook.get("targetPrefix", key)

    timestamp = time.strftime("%Y%m%d-%H:%M")
    outputName = targetPrefix + "@" + timestamp + ".ipynb"

    logger.debug(f"Source Path: {sourcePath}")
    sourcePath = sourcePath.replace("$ORBIT_TRANSFORMATION_NOTEBOOKS_ROOT", "/opt/transformations/")
    workdir = os.path.abspath(sourcePath)

    pathToNotebook = os.path.join(sourcePath, notebookName)

    pathToNotebookFixed = os.path.join("/tmp", outputName)
    logger.debug("Source Notebook: %s", pathToNotebook)

    try:
        sm_notebook = json.loads(open(pathToNotebook).read())
    except Exception as e:
        logger.error("error opening notebook file at: %s", pathToNotebook)
        logger.error(e)
        raise

    if sm_notebook["metadata"]["kernelspec"]["name"] == "sparkkernel":
        sm_notebook["metadata"]["kernelspec"]["language"] = "scala"
    else:
        sm_notebook["metadata"]["kernelspec"]["language"] = "python"
    # if sm_notebook['metadata']['kernelspec']['name'] == 'conda_python3':
    #     sm_notebook['metadata']['kernelspec']['name'] = 'python3'
    with open(pathToNotebookFixed, "w") as outfile:
        json.dump(sm_notebook, outfile)

    logger.debug("fixed language in notebook: %s", pathToNotebook)

    pathToOutputDir = targetPath  # os.path.join(outputDirectory, targetPath)
    logger.info(f"pathToOutputDir={pathToOutputDir}")
    if not targetPath.startswith("s3:") and not os.path.exists(pathToOutputDir):
        pathToOutputDir = os.path.abspath(pathToOutputDir)
        logger.info(f"creating dirs pathToOutputDir={pathToOutputDir}")
        os.makedirs(pathToOutputDir, exist_ok=True)

    notebookNameWithoutSufix = notebookName.split(".")[0]
    pathToOutputNotebookDir = os.path.join(pathToOutputDir, notebookNameWithoutSufix)

    if not targetPath.startswith("s3:") and not os.path.exists(pathToOutputNotebookDir):
        pathToOutputNotebookDir = os.path.abspath(pathToOutputNotebookDir)
        logger.info(f"creating dirs pathToOutputNotebookDir={pathToOutputDir}")
        os.makedirs(pathToOutputNotebookDir, exist_ok=True)

    pathToOutputNotebook = os.path.join(pathToOutputNotebookDir, outputName)

    logger.debug("Target Notebook path: %s", pathToOutputNotebook)
    logger.debug("FOUND notebook: %s", notebook)
    if "paramPath" in notebook:
        pathToParamPath = os.path.abspath(notebook["paramPath"])
        try:
            parameters = read_yaml_file(pathToParamPath)
        finally:
            logger.error("cannot find parameter file at: %s", pathToParamPath)
    elif "params" in notebook:
        try:
            parameters = notebook["params"]
        finally:
            logger.error("fail to parse parameters: %s", notebook["params"])
    else:
        parameters = dict()

    parameters["PAPERMILL_INPUT_PATH"] = os.path.abspath(pathToNotebookFixed)
    parameters["PAPERMILL_OUTPUT_PATH"] = pathToOutputNotebook
    parameters["PAPERMILL_OUTPUT_DIR_PATH"] = pathToOutputNotebookDir
    parameters["PAPERMILL_WORKBOOK_NAME"] = outputName
    parameters["PAPERMILL_WORK_DIR"] = os.path.abspath(workdir)
    logger.debug("runtime parameters: %s", parameters)

    return parameters
