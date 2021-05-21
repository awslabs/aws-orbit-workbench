---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: integration
permalink: integrations/glue-data-brew
title: AWS Glue Data Brew
image: ../img/service/AWS-GlueDataBrew.png
whatIs: "AWS Glue DataBrew is a visual data preparation tool that enables users to clean and normalize data without writing any code. Using DataBrew helps reduce the time it takes to prepare data for analytics and machine learning (ML) by up to 80 percent, compared to custom developed data preparation. You can choose from over 250 ready-made transformations to automate data preparation tasks, such as filtering anomalies, converting data to standard formats, and correcting invalid values."
---
AWS Glue DataBrew is installed as a plugin to the JupyterLab environment.  This means that you can use AWS Glue DataBrew
from within your JupyterLab environment.  Some features of AWS Glue Data Brew are shown below integrated with, 
AWS Orbit Workbench.  You can find out more about AWS Glue DataBrew by looking at the [documentation](AWS Glue DataBrew Developer Guide).  

## Project

<img src="../img/jupyterlab/gluedatabrew/orbit_jupyterlab_glue_databrew_project.png" alt="AWS Glue Data Brew" width="500" style="float: right; margin: 1rem; margin-top: 0" />
The interactive data preparation workspace in DataBrew is called a project. Using a data project, you manage a collection
of related items: data, transformations, and scheduled processes. As part of creating a project, you choose or create a 
dataset to work on. Next, you create a recipe, which is a set of instructions or steps that you want DataBrew to act on. 
These actions transform your raw data into a form that is ready to be consumed by your data pipeline.  You can access you
AWS Glue DataBrew projects directly from AWS Orbit Workbench and use them to work on your data.
<div style="clear: both"></div>

## Profile
<img src="../img/jupyterlab/gluedatabrew/orbit_jupyterlab_glue_databrew_dataprofile.png" alt="AWS Glue Data Brew" width="500" style="float: left; margin: 1rem; margin-top: 0" />
When you profile your data, DataBrew creates a report called a data profile. This summary tells you about the existing 
shape of your data, including the context of the content, the structure of the data, and its relationships. You can make a 
data profile for any dataset by running a data profile job.

<div style="clear: both"></div>

## Data Lineage

<img src="../img/jupyterlab/gluedatabrew/orbit_jupyterlab_glue_databrew_job_datalineage.png" alt="AWS Glue Data Brew" width="500" style="float: right; margin: 1rem; margin-top: 0" />
DataBrew tracks your data in a visual interface to determine its origin, called a data lineage. This view shows you how 
the data flows through different entities from where it originally came. You can see its origin, other entities it was
influenced by, what happened to it over time, and where it was stored.
<div style="clear: both"></div>


