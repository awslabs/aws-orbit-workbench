import json
import sys
import os
import json
import time

import tempfile
import requests
import papermill as pm
import yaml as yaml
import logging
import time
import boto3
import shutil
from multiprocessing import *
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# Hack to make YAML loader not auto-convert datetimes
# https://stackoverflow.com/a/52312810
NoDatesSafeLoader = yaml.SafeLoader
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != 'tag:yaml.org,2002:timestamp'] for
    k, v in NoDatesSafeLoader.yaml_implicit_resolvers.items()
}


def read_yaml_file(path):
    with open(path, 'r') as f:
        return yaml.load(f, Loader=NoDatesSafeLoader)


def run():

    default_output_directory = os.environ.get('output', 'private/outputs')

    notebooks = yaml.load(os.environ['tasks'], Loader=NoDatesSafeLoader)
    compute = yaml.load(os.environ['compute'], Loader=NoDatesSafeLoader)

    notebooksToRun = prepareAndValidateNotebooks(default_output_directory, notebooks)

    try:
        errors = runNotebooks(notebooksToRun, compute)

    finally:
        if len(errors) > 0:
            logger.error("Excution had errors : %s", errors)
            raise Exception("Excution had errors : " + str(errors))
        else:
            return "done notebook execution"



def runNotebooks(reportsToRun, compute):
    errors = []
    if ('container' in compute['compute'].keys() and 'p_concurrent' in compute['compute']['container']):
        workers = int(compute['compute']['container']['p_concurrent'])
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
    try:
        logger.info("Starting notebook execution for %s", parameters['PAPERMILL_OUTPUT_PATH'])
        pm.execute_notebook(
            input_path=parameters['PAPERMILL_INPUT_PATH'],
            output_path=parameters['PAPERMILL_OUTPUT_PATH'],
            parameters=parameters,
            cwd=parameters['PAPERMILL_WORK_DIR'],
            log_output=True
        )
    except Exception as e:
        logger.error("Error during notebook execution: %s", e)
        pathToOutputNotebookError = os.path.join(parameters['PAPERMILL_OUTPUT_DIR_PATH'],
                                                 "error@" + parameters['PAPERMILL_WORKBOOK_NAME'])

        logger.error("tagging error notebook with error %s->%s", parameters['PAPERMILL_OUTPUT_PATH'], pathToOutputNotebookError)
        errors.append(e)
        if parameters['PAPERMILL_OUTPUT_PATH'].startswith("s3:"):
            c = "aws s3 mv {} {}".format(parameters['PAPERMILL_OUTPUT_PATH'], pathToOutputNotebookError)
            print (c)
            os.system(c)
        else:
            shutil.move(parameters['PAPERMILL_OUTPUT_PATH'], pathToOutputNotebookError)

    logger.info("Completed notebook execution: %s", parameters['PAPERMILL_OUTPUT_PATH'])
    return errors

def prepareAndValidateNotebooks(default_output_directory, notebooks):
    reportsToRun = []
    id = 1
    for notebook in notebooks['tasks']:
        key = "e{}".format(str(id))
        id += 1
        reportToRun = prepareNotebook(default_output_directory, notebook, key)
        reportsToRun.append(reportToRun)
    return reportsToRun


def prepareNotebook(default_output_directory, notebook, key):
    notebookName = notebook['notebookName']
    sourcePath = notebook['sourcePath']
    targetPath = notebook.get('targetPath', default_output_directory)
    targetPrefix = notebook.get('targetPrefix', key)

    timestamp = time.strftime("%Y%m%d-%H:%M")
    outputName = targetPrefix + "@" + timestamp + ".ipynb"

    logger.debug(f"Source Path: {sourcePath}")
    sourcePath = sourcePath.replace("$DATAMAKER_TRANSFORMATION_NOTEBOOKS_ROOT", "/opt/transformations/")
    workdir = os.path.abspath(sourcePath)

    pathToNotebook = os.path.join(sourcePath, notebookName)

    pathToNotebookFixed = os.path.join("/tmp", outputName)
    logger.debug("Source Notebook: %s", pathToNotebook)

    try:
        sm_notebook = json.loads(open(pathToNotebook).read())
    except:
        logger.error("cannot find notebook file at: %s", pathToNotebook)
        raise

    if sm_notebook['metadata']['kernelspec']['name'] == 'sparkkernel':
        sm_notebook['metadata']['kernelspec']['language'] = 'scala'
    else:
        sm_notebook['metadata']['kernelspec']['language'] = 'python'
    # if sm_notebook['metadata']['kernelspec']['name'] == 'conda_python3':
    #     sm_notebook['metadata']['kernelspec']['name'] = 'python3'
    with open(pathToNotebookFixed, 'w') as outfile:
        json.dump(sm_notebook, outfile)

    logger.debug("fixed language in notebook: %s", pathToNotebook)

    pathToOutputDir = targetPath # os.path.join(outputDirectory, targetPath)

    if not targetPath.startswith("s3:") and not os.path.exists(pathToOutputDir):
        pathToOutputDir = os.path.abspath(pathToOutputDir)
        os.mkdir(pathToOutputDir)

    notebookNameWithoutSufix = notebookName.split('.')[0]
    pathToOutputNotebookDir = os.path.join(pathToOutputDir, notebookNameWithoutSufix)

    if not targetPath.startswith("s3:") and not os.path.exists(pathToOutputNotebookDir):
        pathToOutputNotebookDir = os.path.abspath(pathToOutputNotebookDir)
        os.mkdir(pathToOutputNotebookDir)

    pathToOutputNotebook = os.path.join(pathToOutputNotebookDir, outputName)

    logger.debug("Target Notebook path: %s", pathToOutputNotebook)
    logger.debug("FOUND notebook: %s", notebook)
    if 'paramPath' in notebook:
        pathToParamPath = os.path.abspath(notebook['paramPath'])
        try:
            parameters = read_yaml_file(pathToParamPath)
        except:
            logger.error("cannot find parameter file at: %s", pathToParamPath)
            raise
    elif 'params' in notebook:
        try:
            parameters = notebook['params']
        except:
            logger.error("fail to parse parameters: %s", notebook['params'])
            raise
    else:
        parameters = dict()

    parameters['PAPERMILL_INPUT_PATH'] = os.path.abspath(pathToNotebookFixed)
    parameters['PAPERMILL_OUTPUT_PATH'] = pathToOutputNotebook
    parameters['PAPERMILL_OUTPUT_DIR_PATH'] = pathToOutputNotebookDir
    parameters['PAPERMILL_WORKBOOK_NAME'] = outputName
    parameters['PAPERMILL_WORK_DIR'] = os.path.abspath(workdir)
    logger.debug("runtime parameters: %s", parameters)

    return parameters
