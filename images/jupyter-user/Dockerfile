FROM jupyter/base-notebook:python-3.8.6

USER root

# System Packages
RUN apt-get update -y
RUN apt-get install sudo -y
RUN apt-get install apt-utils -y
RUN apt-get install build-essential -y
RUN apt-get install curl -y
RUN apt-get install zip unzip -y
RUN apt-get install vim -y
RUN apt-get install less -y
RUN apt-get install jq -y
RUN apt-get install git -y

# Container Run
ADD python-utils/ /opt/python-utils/
RUN chmod -R 755 /opt/python-utils/
ADD transformations/ /opt/transformations/
RUN chmod -R 755 /opt/transformations/

USER $NB_UID

# Python packages
RUN conda update conda
ADD requirements-sys.txt /etc/jupyter/requirements-sys.txt
ADD requirements-sys.txt /etc/jupyter/requirements-kernel-base.txt
RUN conda install --file /etc/jupyter/requirements-sys.txt

# Jpyter Environment configuration
RUN mkdir -p /home/jovyan/.local/share/jupyter 
RUN chown -R jovyan /home/jovyan/.local/share/jupyter
ADD jupyter_server_config.py /home/jovyan/.jupyter/jupyter_server_config.py
ADD bootstrap.sh /etc/jupyterhub/bootstrap.sh

# Create Python 3.6 conda environment and kernel
RUN conda create --name python-3.6 python=3.6.12
RUN conda install --name python-3.6 --file /etc/jupyter/requirements-kernel-base.txt
# ~/.local/share/jupyter/kernels/python-3.6/kernel.json
RUN conda run --name python-3.6 \
    python -m ipykernel install --user --name python-3.6 --display-name "Python 3.6" \
    --env CONDA_PROMPT_MODIFIER 'python-3.6' \
    --env CONDA_PREFIX /opt/conda/envs/python-3.6 \
    --env CONDA_SHLVL 2 \
    --env CONDA_DEFAULT_ENV python-3.6 \
    --env CONDA_PREFIX_1 /opt/conda \
    --env PATH /opt/conda/envs/python-3.6/bin:/opt/conda/condabin:/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Create Python 3.7 conda environment and kernel
RUN conda create --name python-3.7 python=3.7.9
RUN conda install --name python-3.7 --file /etc/jupyter/requirements-kernel-base.txt
# ~/.local/share/jupyter/kernels/python-3.7/kernel.json
RUN conda run --name python-3.7 \
    python -m ipykernel install --user --name python-3.7 --display-name "Python 3.7" \
    --env CONDA_PROMPT_MODIFIER 'python-3.7' \
    --env CONDA_PREFIX /opt/conda/envs/python-3.7 \
    --env CONDA_SHLVL 3 \
    --env CONDA_DEFAULT_ENV python-3.7 \
    --env CONDA_PREFIX_1 /opt/conda \
    --env PATH /opt/conda/envs/python-3.7/bin:/opt/conda/condabin:/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Create Python 3.8 conda environment and kernel
RUN conda create --name python-3.8 python=3.8.6
RUN conda install --name python-3.8 --file /etc/jupyter/requirements-kernel-base.txt
# ~/.local/share/jupyter/kernels/python-3.8/kernel.json
RUN conda run --name python-3.8 \
    python -m ipykernel install --user --name python-3.8 --display-name "Python 3.8" \
    --env CONDA_PROMPT_MODIFIER 'python-3.8' \
    --env CONDA_PREFIX /opt/conda/envs/python-3.8 \
    --env CONDA_SHLVL 1 \
    --env CONDA_DEFAULT_ENV python-3.8 \
    --env CONDA_PREFIX_1 /opt/conda \
    --env PATH /opt/conda/envs/python-3.8/bin:/opt/conda/condabin:/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Replace default kernel (python3) by python-3.8 
RUN cp /home/jovyan/.local/share/jupyter/kernels/python-3.8/kernel.json /opt/conda/share/jupyter/kernels/python3/kernel.json
RUN rm -rf /home/jovyan/.local/share/jupyter/kernels/python-3.8/kernel.json

# Necessary to install packages from CodeArtifact
ADD pip.conf /etc/pip.conf
RUN conda run pip install --upgrade aws-orbit-sdk
RUN conda run --name python-3.6 pip install --upgrade aws-orbit-sdk
RUN conda run --name python-3.7 pip install --upgrade aws-orbit-sdk
RUN conda run --name python-3.8 pip install --upgrade aws-orbit-sdk
USER root
RUN rm /etc/pip.conf
USER $NB_UID

# Jupyter Lab extensions
ENV JUPYTER_ENABLE_LAB yes
RUN jupyter serverextension enable --py jupyterlab --sys-prefix
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager --no-build
RUN jupyter lab build
