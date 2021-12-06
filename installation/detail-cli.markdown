---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: CLI
permalink: detail-cli
---

# Install the Oribt Workbench Command Line Interface (CLI)


#### Prerequisites
- cloned the [AWS Labs github repository](detail-clone)
- Python 3.7 should be installed

<br>

----
## **Steps**
1. Go to the cloned repo
    ```
    cd <cloned_repo_dir>/aws-orbit-workbench/cli
    ```
2. Create and activate a Python virtual environment for the CLI
    ```
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3. Install the AWS Orbit Workbench CLI and dependancies
    ```
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install -e .
    ```
