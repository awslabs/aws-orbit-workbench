---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Creating reusable Conda Environments using FSX file storage 
permalink: reusing-conda-environments
---

## Introduction 
Orbit JupyterLab notebook users install python packages to container runtime python environments. Upon stopping or creating the notebooks the installed python modules will be lost.

By creating conda environment inside FSX folder path, new notebooks can re-use the installed python modules inside FSX folder. Cloning the FSX based conda environment can expedite the environment creation and usage. 

## Check availability of .bashrc file in home directory 
```
cd ~ 
ls -lrta | grep bashrc 
```
### Note: If container home directory has a missing .bashrc, user can copy from /opt/orbit/bashrc 
```cp /opt/orbit/bashrc ~/.bashrc```

## Activate bash profile 
```source ~/.bashrc```


## Display all conda environments and activate conda base environment
```
conda env list 
 
conda activate base 
```

## Add fsx path to the conda envs directories

```conda config  --prepend envs_dirs  /fsx/condaenvs```

## verify conda env directories from info 

```conda info```

## Clone coda environment from base environment to fsx path

```conda create --clone base --name conda_env_clone_example``` 

## Activate cloned conda environment 

```conda activate conda_env_clone_example```

## Add cloned conda environment to Jupyter Lab kernels"

```
conda install -c anaconda ipykernel --force-reinstall

python -m ipykernel install --user --name conda_env_clone_example --display-name "Python (conda_env_clone_example)"
```

##  Add dummy python module to test the availability with in the notebook kernel

```pip install python-dummy --force-reinstall```


## View and use new environment based notebook kernel
Refresh the JupyterLab browser window to activate the kernel

