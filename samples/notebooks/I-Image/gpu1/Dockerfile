FROM cschranz/gpu-jupyter:v1.3_cuda-10.1_ubuntu-18.04_python-only

######################################
# System
######################################

USER root

RUN apt-get update && apt-get install -yq --no-install-recommends \
    apt-utils \
    build-essential \
    vim-tiny \
    nano-tiny \
    git \
    netcat \
    tzdata \
    unzip \
    sudo \
    curl \
    zip \
    less \
    jq \
    # ---- Cleaning up ----
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/nano nano /bin/nano-tiny 10

######################################
# Kubectl installation
######################################
RUN cd /usr/local/bin \
    && sudo curl -k -sS -O https://amazon-eks.s3.us-west-2.amazonaws.com/1.18.9/2020-11-02/bin/linux/amd64/kubectl \
    && sudo chmod 755 /usr/local/bin/kubectl

######################################
# Container Run
######################################

ADD python-utils/ /opt/python-utils/
RUN chmod -R 755 /opt/python-utils/
ADD transformations/ /opt/transformations/
RUN chmod -R 755 /opt/transformations/

######################################
# Jupyter Environment configuration
######################################

RUN mkdir -p /home/jovyan/.local/share/jupyter
RUN chown -R jovyan /home/jovyan/.local/share/jupyter
ADD jupyter_server_config.py /home/jovyan/.jupyter/jupyter_server_config.py

######################################
# Python/Conda packages
######################################

ADD requirements.txt /etc/jupyter/requirements.txt
RUN conda run pip install -r /etc/jupyter/requirements.txt && \
    conda clean --all -f -y

######################################
# Python/Conda packages from CODEARTIFACT
######################################

ADD pip.conf /etc/pip.conf
RUN conda run pip install --upgrade aws-orbit aws-orbit-sdk
RUN rm /etc/pip.conf

# remove the auto includes with the kubespawner package as we just using the helper class.
RUN conda run pip install --no-deps jupyterhub-kubespawner~=0.15.0
RUN echo "" > `conda run pip  show jupyterhub-kubespawner | grep "Location:" | cut -d ':' -f 2`/kubespawner/__init__.py

# add the boostrap script and change permission to jovyan
RUN mkdir -p /home/jovyan/.orbit
ADD bootstrap.sh /home/jovyan/.orbit/bootstrap.sh
RUN chown -R jovyan /home/jovyan/.orbit
RUN chmod a+xr /home/jovyan/.orbit/bootstrap.sh

# ######################################
# # Jupyter Lab extensions
# ######################################

ENV JUPYTER_ENABLE_LAB yes
RUN jupyter serverextension enable --py jupyterlab --sys-prefix && \
    jupyter nbextension enable --py widgetsnbextension --sys-prefix && \
    jupyter labextension install @jupyter-widgets/jupyterlab-manager --no-build --no-build && \
    jupyter labextension install jupyter-matplotlib --no-build && \
    jupyter lab build --dev-build=False -y && \
    jupyter lab clean -y && \
    npm cache clean --force && \
    rm -rf "/home/${NB_USER}/.cache/yarn" && \
    rm -rf "/home/${NB_USER}/.node-gyp" && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER $NB_UID