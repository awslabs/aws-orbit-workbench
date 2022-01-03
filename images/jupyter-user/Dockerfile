
ARG BASE_IMAGE=public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter/base-notebook:python-3.8.8
FROM $BASE_IMAGE as base

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
    rsync \
    # ---- Cleaning up ----
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/nano nano /bin/nano-tiny 10

#=================   END base  =================

FROM base AS tools

# Kubectl installation
RUN cd /usr/local/bin \
    && sudo curl -k -sS -O https://amazon-eks.s3.us-west-2.amazonaws.com/1.19.6/2021-01-05/bin/linux/amd64/kubectl \
    && sudo chmod 755 /usr/local/bin/kubectl

# Helm installation
RUN curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash && \
    helm version --short && \
    helm plugin install https://github.com/hypnoglow/helm-s3.git && \
    helm repo add stable https://charts.helm.sh/stable

# Container Run
ADD python-utils/ /opt/python-utils/
RUN chmod -R 755 /opt/python-utils/
ADD transformations/ /opt/transformations/
RUN chmod -R 755 /opt/transformations/

# add the boostrap script and change permission to jovyan
RUN mkdir -p /opt/orbit
ADD bashrc /opt/orbit/bashrc
RUN chown -R jovyan /opt/orbit

#=================   END tools  =================

FROM tools AS conda

# Python/Conda packages

ADD requirements.txt /etc/jupyter/requirements.txt
RUN conda run pip install -r /etc/jupyter/requirements.txt && \
    conda clean --all -f -y

#=================   END conda  =================

FROM conda AS lab


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

#=================   END lab  =================

FROM lab as databrew

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

#=================   END databrew  =================

FROM databrew AS vscode

#Add in VSCode support
RUN mkdir -p /opt/orbit/codeserver_proxy
COPY codeserver_proxy /opt/orbit/codeserver_proxy
RUN chmod -R a+xr /opt/orbit/codeserver_proxy/*.sh
RUN chown -R jovyan /opt/orbit/codeserver_proxy
WORKDIR /opt/orbit/codeserver_proxy
RUN /opt/orbit/codeserver_proxy/install.sh
RUN chown -R jovyan /opt/orbit/codeserver_proxy


#=================   END vscode  =================

FROM vscode AS smlogs

# Install SM-LOGS   REF: https://docs.aws.amazon.com/sagemaker/latest/dg/amazon-sagemaker-operators-for-kubernetes.html
RUN mkdir /opt/orbit/sm-logs && \
    cd /opt/orbit/sm-logs
RUN curl -k -sS -O https://s3.us-west-2.amazonaws.com/amazon-sagemaker-operator-for-k8s-us-west-2/kubectl-smlogs-plugin/v1/linux.amd64.tar.gz && \
    tar xvzf linux.amd64.tar.gz && \
    sudo mv ./kubectl-smlogs.linux.amd64/kubectl-smlogs /usr/local/bin && \
    sudo chmod 755 /usr/local/bin/kubectl-smlogs
RUN cd /opt/orbit && \
    rm -rf /opt/orbit/sm-logs


FROM smlogs AS orbit-libs

# add bundle with docker image sources
COPY aws-orbit_jupyter-user.tar.gz /opt/orbit/aws-orbit_jupyter-user.tar.gz
RUN chown jovyan /opt/orbit/aws-orbit_jupyter-user.tar.gz
WORKDIR /opt/orbit/
RUN tar xvzf /opt/orbit/aws-orbit_jupyter-user.tar.gz
WORKDIR /opt/orbit/aws-orbit_jupyter-user

ADD pip.conf /etc/pip.conf
RUN conda run pip install -r /opt/orbit/aws-orbit_jupyter-user/aws-orbit/requirements.txt
RUN conda run pip install /opt/orbit/aws-orbit_jupyter-user/aws-orbit
RUN conda run pip install /opt/orbit/aws-orbit_jupyter-user/aws-orbit-sdk
RUN conda run pip install /opt/orbit/aws-orbit_jupyter-user/jupyterlab_orbit
RUN conda run pip install aws-codeseeder
RUN rm /etc/pip.conf

#RUN rm -rf /opt/orbit/aws-orbit_jupyter-user

RUN fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

WORKDIR /home/${NB_USER}

USER $NB_UID
