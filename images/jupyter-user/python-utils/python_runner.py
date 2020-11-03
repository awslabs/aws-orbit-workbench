import sys
import os
import time
import git
import tempfile
import requests
import yaml as yaml
import logging
import time
import boto3
from multiprocessing import *
from importlib import import_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def run():
    repo_dir_code = os.environ['AWS_DATAMAKER_REPO']

    outputDirectory = os.environ['s3_output']

    repos_url = os.environ['repos_url']
    tasks = yaml.load(os.environ['tasks'], Loader=NoDatesSafeLoader)
    compute = yaml.load(os.environ['compute'], Loader=NoDatesSafeLoader)

    prepareLocalEnv(repos_url, repo_dir_code, outputDirectory)

    errors = []
    try:
        errors = runTasks(tasks['tasks'],compute)

    finally:
        if len(errors) > 0:
            logger.error("Excution had errors : %s", errors)
            raise Exception("Excution had errors : " + str(errors))

    return "done notebook execution"


def runTasks(tasks, compute):
    errors = []
    if ('container' in compute['compute'].keys() and 'p_concurrent' in compute['compute']['container']):
        workers = int(compute['compute']['container']['p_concurrent'])
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
    parameters = task['params']
    module = task['module']
    functionName = task['functionName']
    sourcePaths = task['sourcePaths']
    for p in sourcePaths:
        sys.path.insert(0, os.path.join("/ws", p))

    logger.info("import paths: %s" , str(sys.path))

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


def prepareLocalEnv(repos_url, repo_dir_code, outputDirectory):
    if not os.path.exists("/ws"):
        os.mkdir("/ws")
    os.chdir("/ws")

    if not os.path.exists(repo_dir_code):
        logger.info("cloning repositories: %s", repos_url + repo_dir_code)
        
        git.Repo.clone_from(repos_url + repo_dir_code, repo_dir_code)
        if (not outputDirectory.startswith("s3:")):
            git.Repo.clone_from(repos_url + outputDirectory, outputDirectory)
    else:
        logger.info("pulling code changes for code repository: %s", repos_url + repo_dir_code)
        g = git.cmd.Git(repo_dir_code)
        g.pull()

# Hack to make YAML loader not auto-convert datetimes
# https://stackoverflow.com/a/52312810
NoDatesSafeLoader = yaml.SafeLoader
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != 'tag:yaml.org,2002:timestamp'] for
    k, v in NoDatesSafeLoader.yaml_implicit_resolvers.items()
}


