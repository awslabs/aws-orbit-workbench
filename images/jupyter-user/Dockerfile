ARG BASE_IMAGE=public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter/base-notebook:python-3.8.8
FROM $BASE_IMAGE

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
    && sudo curl -k -sS -O https://amazon-eks.s3.us-west-2.amazonaws.com/1.19.6/2021-01-05/bin/linux/amd64/kubectl \
    && sudo chmod 755 /usr/local/bin/kubectl

######################################
# Helm installation
######################################
RUN curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash && \
    helm version --short && \
    helm plugin install https://github.com/hypnoglow/helm-s3.git && \
    helm repo add stable https://charts.helm.sh/stable

######################################
# Container Run
######################################

ADD python-utils/ /opt/python-utils/
RUN chmod -R 755 /opt/python-utils/
ADD transformations/ /opt/transformations/
RUN chmod -R 755 /opt/transformations/

# add the boostrap script and change permission to jovyan
RUN mkdir -p /opt/orbit
ADD bootstrap.sh /opt/orbit/bootstrap.sh
RUN chown -R jovyan /opt/orbit
RUN chmod a+xr /opt/orbit/bootstrap.sh

######################################
# Jupyter Environment configuration
######################################

#RUN mkdir -p /home/jovyan/.local/share/jupyter
#RUN chown -R jovyan /home/jovyan/.local/share/jupyter
#ADD jupyter_server_config.py /home/jovyan/.jupyter/jupyter_server_config.py

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
ADD VERSION /opt/orbit/VERSION
RUN chown jovyan /opt/orbit/VERSION
RUN conda run pip install --upgrade \
    aws-orbit==$(cat /opt/orbit/VERSION) \
    aws-orbit-sdk==$(cat /opt/orbit/VERSION)
RUN rm /etc/pip.conf

# add the boostrap script and change permission to jovyan
RUN mkdir -p /opt/orbit
ADD bootstrap.sh /opt/orbit/bootstrap.sh
RUN chown -R jovyan /opt/orbit
RUN chmod a+xr /opt/orbit/bootstrap.sh

# add bundle with docker image sources
COPY aws-orbit_jupyter-user.tar.gz /opt/orbit/aws-orbit_jupyter-user.tar.gz
RUN chown jovyan /opt/orbit/aws-orbit_jupyter-user.tar.gz



# ######################################
# # Jupyter Lab extensions
# ######################################

ENV JUPYTER_ENABLE_LAB yes
RUN jupyter serverextension enable --py jupyterlab --sys-prefix && \
    jupyter serverextension enable --sys-prefix jupyter_server_proxy && \
    jupyter nbextension enable --py widgetsnbextension --sys-prefix && \
    jupyter labextension install @jupyter-widgets/jupyterlab-manager --no-build && \
    jupyter labextension install jupyter-matplotlib --no-build && \
    jupyter labextension install @jupyterlab/server-proxy --no-build && \
    jupyter lab build --dev-build=False -y && \
    jupyter lab clean -y && \
    npm cache clean --force && \
    rm -rf "/home/${NB_USER}/.cache/yarn" && \
    rm -rf "/home/${NB_USER}/.node-gyp" && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

ADD extensions/jupyterlab_orbit/ /etc/extensions/jupyterlab_orbit/

RUN mkdir -p /opt/orbit/databrew
COPY aws-glue-databrew-jupyter-extension.tar.gz /opt/orbit/databrew/aws-glue-databrew-jupyter-extension.tar.gz

WORKDIR /opt/orbit/databrew
RUN tar xvzf aws-glue-databrew-jupyter-extension.tar.gz

WORKDIR /opt/orbit/databrew/aws-glue-databrew-jupyter-extension/

RUN npm install && \
    npm run build && \
    conda run pip install ./ && \
    jupyter labextension install ./ && \
    jupyter lab build

WORKDIR /opt/orbit/databrew
RUN rm -rf ./databrew

#Add in VSCode support
RUN mkdir -p /opt/orbit/codeserver_proxy
COPY codeserver_proxy /opt/orbit/codeserver_proxy
RUN chmod -R a+xr /opt/orbit/codeserver_proxy/*.sh
RUN chown -R jovyan /opt/orbit/codeserver_proxy
WORKDIR /opt/orbit/codeserver_proxy
RUN /opt/orbit/codeserver_proxy/install.sh
<<<<<<< HEAD
=======
RUN chown -R jovyan /opt/orbit/codeserver_proxy
>>>>>>> main


WORKDIR /home/${NB_USER}

RUN conda run pip install /etc/extensions/jupyterlab_orbit/

RUN jupyter labextension build /etc/extensions/jupyterlab_orbit

USER $NB_UID
