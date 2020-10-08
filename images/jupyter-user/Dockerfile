FROM jupyterhub/k8s-singleuser-sample:0.9.1

# System Packages
USER root
RUN apt-get update -y
RUN apt-get install sudo -y
RUN apt-get install apt-utils -y 
RUN apt-get install build-essential -y
RUN apt-get install curl -y
USER $NB_UID

# General Python packages
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --upgrade wheel
RUN python3 -m pip install --upgrade awscli
RUN python3 -m pip install --upgrade notebook
RUN python3 -m pip install --upgrade jupyterlab
RUN python3 -m pip install --upgrade kubernetes~=11.0.0
RUN python3 -m pip install --upgrade papermill~=2.1.3

ADD requirements.txt /etc/jupyterhub/requirements.txt
RUN python3 -m pip install --use-feature=2020-resolver --requirement /etc/jupyterhub/requirements.txt

# DataMaker package
RUN mkdir .datamaker
ADD sdk/setup.py .datamaker/setup.py
ADD sdk/datamaker .datamaker/datamaker
RUN python3 -m pip install -e .datamaker/

# Jupyter Lab extensions
ENV JUPYTER_ENABLE_LAB true
RUN jupyter serverextension enable --py jupyterlab --sys-prefix
RUN python3 -m pip install jupyterlab-s3-browser
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager jupyterlab-s3-browser @8080labs/qgrid --no-build
RUN jupyter serverextension enable --py jupyterlab_s3_browser

#theme
ADD theme /etc/jupyterhub/theme
WORKDIR /etc/jupyterhub/theme
USER root
RUN npm install
RUN npm run build
RUN chown -R $NB_USER /etc/jupyterhub/theme
USER $NB_UID
RUN jupyter labextension install . --no-build
WORKDIR $HOME

# schedule
ADD schedule /etc/jupyterhub/schedule
WORKDIR /etc/jupyterhub/schedule
USER root
RUN jlpm
RUN chown -R $NB_USER /etc/jupyterhub/schedule
USER $NB_UID
RUN jlpm build
RUN pip install .
RUN jupyter serverextension enable --py schedule
RUN jupyter labextension install . --no-build
WORKDIR $HOME

RUN jupyter lab build

# EFS
ADD link-user-efs-directory.sh /etc/jupyterhub/link-user-efs-directory.sh

# Scheduled notebook executions
ADD execute-notebook.py /etc/jupyterhub/execute-notebook.py

# Jupyter Lab settings
ADD overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json
