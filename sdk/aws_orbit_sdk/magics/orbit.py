import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Union

import IPython.core.display
from IPython import get_ipython
from IPython.core.magic import Magics, cell_magic, line_cell_magic, line_magic, magics_class, needs_local_scope

from aws_orbit_sdk import controller
from aws_orbit_sdk.json import display_json, run_schema_induction_args


def exception_handler(exception_type, exception, traceback):
    print("%s: %s" % (exception_type.__name__, exception), file=sys.stderr)


class ArgumentParserNoSysExit(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        raise Exception(message)


@magics_class
class OrbitWorkbenchMagics(Magics):
    def __init__(self, shell):
        super(OrbitWorkbenchMagics, self).__init__(shell)
        self.ip = get_ipython()

    @line_magic
    def schema_induction(self, line: str) -> Dict[str, Union[str, Dict[str, str]]]:
        """
        Calls on run_process to run Schema Induction with given user arguments gets ddl and schema metadata for a
        specified table.

        Parameters
        ----------
        User parameters including:
        '-i' : str
            An input json file path.
        '-c' : str, optional
            Specify compute service to run schema induction (default ec2).
        '-t' : str
            Table name to use when creating DDL.
        '--location' : str
            Table s3 location to use when creating DDL.
        '--root' : str
            The root directory name of the data.
        '-a' : bool, optional
            Is the document a json array (default True).

        Returns
        ----------
        ddl : str
            SQL ddl statement to create new external table with given metadata.
        schema :
            Schema metadata stored as a json for the specified table.

        Example
        ----------
        >>> %schema_induction -i data_path -c ec2 -t table_name --location s3_location --root ClaimData
        """

        lineArgs = line.split(" ")
        return run_schema_induction_args(lineArgs)

    # @needs_local_scope
    # @line_magic
    # def display_grid(self, line: str, local_ns: Optional[Dict[str, str]] = None) -> qgrid.QGridWidget:
    #     """
    #     Renders a DataFrame or Series as an interactive qgrid, represented by an instance of the QgridWidget class.
    #
    #     Parameter
    #     ----------
    #     line : str
    #         Specifies the name of the DataFrame
    #     local_ns : str
    #         The namespace to load into IPython user namespace
    #
    #     Return
    #     ----------
    #     qgrid : qgrid.QGridWidget
    #         A DataFrame or Series shown as an interactive qgrid
    #
    #     Example
    #     ----------
    #     >>> %%sql analysis <<
    #     >>> select * from database.table1
    #
    #     >>> %display_grid analysis
    #     """
    #     lineArgs = line.split(" ")
    #     dataset = local_ns[lineArgs[0]]
    #     return qgrid.show_grid(
    #         dataset.DataFrame(),
    #         show_toolbar=False,
    #         grid_options={
    #             "forceFitColumns": False,
    #             "defaultColumnWidth": 140,
    #             "editable": False,
    #             "autoEdit": False,
    #         },
    #     )

    @needs_local_scope
    @line_magic
    def display_tree(self, line: str, local_ns: Optional[Dict[str, str]] = None) -> IPython.core.display.JSON:
        """

        Parameters
        ----------
        line : str
            Dataset name with data to display
        local_ns : str
            The namespace to load into IPython user namespace

        Returns
        ----------
        tree: IPython.core.display.JSON
        An IPython JSON display representing the data.

        Example
        ----------
        >>> %display_tree dataset
        """

        lineArgs = line.split(" ")
        dataset = local_ns[lineArgs[0]]
        return display_json(dataset)

    @line_magic
    def short_errors(self, line):
        ip = get_ipython()
        ip._showtraceback = exception_handler

    @cell_magic
    def schedule_notebook(self, line: str, cell: str, local_ns: Optional[Dict[str, str]] = None) -> str:
        """
        Schedule a notebook execution.

        Parameters
        ----------
        Line parameters:
            '-cron' : str
                specify cron-based schedule
            '-id' : str
                specify unique identifier for this scheduled task

        Cell parameters:
            'taskConfiguration' : dict
                A task definition to execute
                'notebooks' : list
                    A list of notebook task definition to run
                    'notebookName' : str
                        The filename of the notebook
                    'sourcePath' : str
                        The relative path to the notebook file starting at the repository root
                    'targetPath' : str
                        The target S3 directory where the output notebook and all related output will be generated
                    'params' : dict
                        A list of parameters for this task to override the notebook parameters
                'compute' : dict, optional
                    A list of runtime parameters to control execution
                    'container' : dict
                        A list of parameters to control container execution
                        'p_concurrent' : str
                            The number of parallel threads inside the container that will execute notebooks
                'env_vars' : list, optional
                    A list of environment parameters to pass to the container
                    'container' : dict
                        A list of parameters to control container execution
                        'p_concurrent' : str
                            The number of parallel threads inside the container that will execute notebooks
        local_ns : str
            The namespace to load into IPython user namespace

        Returns
        --------
        response : str
            The response will be ARN of the event rule created to start this execution.

        Example
        -------
        >>> %%schedule_notebook -cron cron(0/3 * 1/1 * ? *)  -id yyy
        >>> {
        >>>      "tasks":  [
        >>>            {
        >>>                  "notebookName": "Example-1-SQL-Analysis-Athena.ipynb",
        >>>                  "sourcePath": "samples/notebooks/B-DataAnalyst",
        >>>                  "targetPath": "tests/Z-Tests/Scheduling",
        >>>                  "targetPrefix": "yyy",
        >>>                  "params": {
        >>>                        "glue_db" : "cms_raw_db",
        >>>                        "target_db" : "users"
        >>>                  }
        >>>            }
        >>>      ]
        >>> }
        """
        if len(line) == 0:
            print("must provide -cron and -id parameters")
            return

        parser = ArgumentParserNoSysExit(description="schedule a task to be executed on container")
        parser.add_argument("-cron", required=True, nargs="+", help="specify cron-based schedule")

        parser.add_argument(
            "-id",
            required=True,
            help="specify unique identifier for this scheduled task",
        )

        try:
            args = parser.parse_args(line.strip().split(" "))
            cronStr = " ".join(args.cron)
            return controller.schedule_notebooks(
                triggerName=args.id,
                frequency=cronStr,
                taskConfiguration=json.loads(cell),
            )
        except Exception as e:
            print("Error!")
            print(str(e))

    @cell_magic
    def run_notebook(self, line: Optional[str], cell: str, local_ns: Optional[Dict[str, str]] = None) -> List[str]:
        """
        Run a notebook execution.

        Parameters
        ----------
        local_ns : str
            The namespace to load into IPython user namespace

        Cell parameters:
            'taskConfiguration' : dict
                A task definition to execute
                'notebooks' : list
                    A list of notebook task definition to run
                    'notebookName' : str
                        The filename of the notebook
                    'sourcePath' : str
                        The relative path to the notebook file starting at the repository root
                    'targetPath' : str
                        The target S3 directory where the output notebook and all related output will be generated
                    'params' : dict
                        A list of parameters for this task to override the notebook parameters
                'compute' : dict, optional
                    A list of runtime parameters to control execution
                    'container' : dict
                        A list of parameters to control container execution
                        'p_concurrent' : str
                            The number of parallel threads inside the container that will execute notebooks
                    'sns.topic.name' : str
                        A name of a topic to which messages are sent on task completion or failure
                'env_vars' : list, optional
                    A list of environment parameters to pass to the container

        Returns
        --------
        response: list
            List of containers ARNs that are started
            (e.g. ['arn:aws:ecs:us-east-1:{accountid}:task/a99f186c-160d-48b8-99de-a51f40f7c78e'])

        Example
        -------
        >>> %%run_notebook
        >>> taskConfiguration = {
        >>> "notebooks":  [ {
        >>>     "notebookName": "Example-2-Extract-Files.ipynb",
        >>>     "sourcePath": "samples/notebooks/A-LakeCreator",
        >>>     "targetPath": "tests/createLake",
        >>>     "params": {
        >>>         "bucketName": bucketName,
        >>>         "zipFileName": file,
        >>>         "targetFolder": extractedFolder
        >>>         },
          ...
        >>> }],
        >>> "compute": {
        >>>     "container" : {
        >>>         "p_concurrent": "4",
        >>>         },
        >>>     "env_vars": [
        >>>                 {
        >>>                     'name': 'cluster_name',
        >>>                     'value': clusterName
        >>>                 }
        >>>     ],
        >>>     "sns.topic.name": 'TestTopic',
        >>> }}
        """
        try:
            return controller.run_notebooks(taskConfiguration=json.loads(cell))
        except Exception as e:
            print("Error!")
            print(str(e))

    @cell_magic
    def run_python(self, line: Optional[str], cell: str, local_ns: Optional[Dict[str, str]] = None) -> List[str]:
        """
        Run some python code.

        Parameters
        ----------
        local_ns : str
            The namespace to load into IPython user namespace

        Cell parameters:
            'taskConfiguration' : dict
                    A task definition to execute
                    'tasks' : list
                        A list of python task definition to run
                        'module' : str
                            The python module to run (without .py ext)
                        'functionName' : str
                            The python function to start the execution
                        'sourcePaths' : list
                            A list of s3 python source paths used for importing packages or modules into the application
                        'params' : dict
                            A list of parameters for this task to override the notebook parameters
                'compute' : dict, optional
                    A list of runtime parameters to control execution
                    'container' : dict
                        A list of parameters to control container execution
                        'p_concurrent' : str
                            The number of parallel threads inside the container that will execute notebooks
                'env_vars' : list, optional
                    A list of environment parameters to pass to the container
                    'container' : dict
                        A list of parameters to control container execution
                        'p_concurrent' : str
                            The number of parallel threads inside the container that will execute notebooks

        Returns
        -------
        response : list
            A list of containers ARNs that are started
            (e.g. ['arn:aws:ecs:us-east-1:{accountid}:task/a9a186c-160d-48b8-99de-a51f40f7c78e'])

        Example
        -------
        >>> taskConfiguration = {
        >>> "tasks":  [
        >>>     {
        >>>       "module": "pyspark.run_pyspark_local",
        >>>       "functionName": "run_spark_job",
        >>>       "sourcePaths": ["DataScienceRepo/samples/python"],
        >>>       "params": {
        >>>                 "bucket": "users-env2",
        >>>                 "p2": 'bar'
        >>>       }
        >>>     }
        >>> ],
        >>> "compute": {
        >>>     "container" : {
        >>>         "p_concurrent": "4"
        >>> },
        >>> "env_vars": [
        >>>             {
        >>>                 'name': 'cluster_name',
        >>>                 'value': clusterName
        >>>             }
        >>> ]
        >>> }}
        """
        try:
            return controller.run_python(taskConfiguration=json.loads(cell))
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def delete_schedule_task(self, line: str) -> None:
        """
        Deletes a scheduled task execution.

        Parameters
        ----------
        '-id' : str
            The arn of the event rule

        Returns
        -------
        None
            None.

        Example
        -------
        >>> %delete_schedule_task -id taskid
        """
        if len(line) == 0:
            print("must provide -id parameter")
            return
        parser = ArgumentParserNoSysExit(description="delete schedule task")
        parser.add_argument(
            "-id",
            required=True,
            help="specify unique identifier for this scheduled task",
        )
        try:
            args = parser.parse_args(line.strip().split(" "))
            return controller.delete_task_schedule(triggerName=args.id)
        except Exception as e:
            print("Error!")
            print(str(e))


# In order to actually use these magics, you must register them with a
# running IPython.
def load_ipython_extension(ipython):
    """
    Any module file that define a function named `load_ipython_extension`
    can be loaded via `%load_ext module.path` or be configured to be
    autoloaded by IPython at startup time.
    """
    # You can register the class itself without instantiating it.  IPython will
    # call the default constructor on it.
    ipython.register_magics(OrbitWorkbenchMagics)


#
# def apt_completers(self, event):
#     """ This should return a list of strings with possible completions.
#
#     Note that all the included strings that don't start with event.symbol
#     are removed, in order to not confuse readline.
#     """
#     return ['update', 'upgrade', 'install', 'remove']
#
#     completerlib.quick_completer('SELECT', ['FROM','WHERE', 'GROUPBY'])
#
#


ip = get_ipython()
magics = OrbitWorkbenchMagics(ip)
ip.register_magics(magics)
