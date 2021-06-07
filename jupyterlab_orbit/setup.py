"""
jupyterlab_orbit setup
"""
import json
import os

import setuptools
from jupyter_packaging import combine_commands, create_cmdclass, ensure_targets, install_npm, skip_if_exists

HERE = os.path.abspath(os.path.dirname(__file__))

# The name of the project
name = "jupyterlab_orbit"

# Get our version
with open(os.path.join(HERE, "VERSION")) as version_file:
    version = version_file.read().strip()

lab_path = os.path.join(HERE, name, "labextension")

# Representative files that should exist after a successful build
jstargets = [
    os.path.join(lab_path, "package.json"),
]

package_data_spec = {name: ["*"]}

labext_name = "jupyterlab_orbit"

data_files_spec = [
    ("share/jupyter/labextensions/%s" % labext_name, lab_path, "**"),
    ("share/jupyter/labextensions/%s" % labext_name, HERE, "install.json"),
    ("etc/jupyter/jupyter_server_config.d", "jupyter-config", "jupyterlab_orbit.json"),
]

cmdclass = create_cmdclass("jsdeps", package_data_spec=package_data_spec, data_files_spec=data_files_spec)

js_command = combine_commands(
    install_npm(HERE, build_cmd="build:prod", npm=["jlpm"]),
    ensure_targets(jstargets),
)

is_repo = os.path.exists(os.path.join(HERE, ".git"))
if is_repo:
    cmdclass["jsdeps"] = js_command
else:
    cmdclass["jsdeps"] = skip_if_exists(jstargets, js_command)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name=f"aws-orbit-{name}".replace("_", "-"),
    version=version,

    author="AWS Professional Services",
    author_email="aws-proserve-opensource@amazon.com",
    url="https://github.com/awslabs/aws-orbit-workbench",
    project_urls={"Org Site": "https://aws.amazon.com/professional-services/"},
    description="AWS Orbit Workbench JupyterLab extension.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    cmdclass=cmdclass,
    packages=setuptools.find_packages(),
    zip_safe=False,
    include_package_data=True,
    python_requires=">=3.7",
    license="Apache License 2.0",
    platforms="Linux, Mac OS X, Windows",
    keywords=["Jupyter", "JupyterLab", "JupyterLab3"],
    install_requires=[
        "jupyterlab>=3.0.0rc13,==3.*",
    ],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Framework :: Jupyter",
    ],
)
