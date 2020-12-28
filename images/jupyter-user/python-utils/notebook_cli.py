from logging import log
import os
import notebook_runner  as nr
import python_runner as pr
import json
import logging
import time
import yaml
import boto3
import subprocess
import sys
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
from os.path import expanduser

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

def writeOrbitYaml():
    data = dict(properties=
        dict(
            AWS_ORBIT_ENV=os.environ['AWS_ORBIT_ENV'],
            ORBIT_TEAM_SPACE=os.environ['ORBIT_TEAM_SPACE'],
        )
    )
    home = expanduser("~")
    propFilePath = f"{home}/orbit.yaml"

    with open(propFilePath, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)

def notifyOnTasksCompletion(subject, msg, compute):
    if 'topic' not in compute['compute'].keys():
        return
    topic_name = compute['compute']['sns.topic.name']
    logger.info(f"sending task notification to {topic_name}...")
    try:
        sns = boto3.client('sns')
        res = sns.list_topics()['Topics']
        for topic in res:
            if topic_name in topic['TopicArn']:
                sns.publish(
                    TopicArn=topic['TopicArn'],
                    Message=msg,
                    Subject=subject
                )

    except:
        print("Unexpected error while publishing to topic:", sys.exc_info()[0])

    logger.info(f"done task notifications to {topic_name}")

def run_tasks():
    logger.debug("starting task execution with following arguments: ")

    env_params = ''
    for param in os.environ.keys():
        env_params += param + " = " + os.environ[param] + "\n"
    logger.debug(env_params)

    writeOrbitYaml()
    compute = yaml.load(os.environ['compute'], Loader=NoDatesSafeLoader)
    task_type = os.environ['task_type']
    try:
        if (task_type == 'jupyter'):
            nr.run()
        else:
            pr.run()
        logger.info("Done task execution")
        notifyOnTasksCompletion("finished executing tasks", 'Tasks:\n' + os.environ['tasks'], compute)
    except Exception as e:
        logger.exception(f"Done task execution with errors, {str(e)}")
        notifyOnTasksCompletion("Error while executing tasks. Errors: \n",
                                str(e) + '\n\n Tasks:\n' + os.environ['tasks'], compute)


def symlink_efs():
    jupyter_user = os.environ.get("JUPYTERHUB_USER", None)
    if jupyter_user:
        logger.info(f"Symlinking /efs/{jupyter_user} to /home/jovyan/private")
        subprocess.check_call(["ln", "-s", f"/efs/{jupyter_user}", "/home/jovyan/private"])
    logger.info("Symlinking /efs/shared /home/jovyan/shared")
    subprocess.check_call(["ln", "-s", "/efs/shared", "/home/jovyan/shared"])


if __name__ == '__main__':
    logger.info("Starting Container Main")
    symlink_efs()
    logger.info("Running tasks...")
    run_tasks()
    logger.info("Exiting Container Main()")
