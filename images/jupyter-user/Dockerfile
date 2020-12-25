FROM jupyterhub/k8s-singleuser-sample:0.9.1

# System Packages
USER root
RUN apt-get update -y
RUN apt-get install sudo -y
RUN apt-get install apt-utils -y
RUN apt-get install build-essential -y
RUN apt-get install curl -y
RUN apt-get install zip unzip -y
RUN apt-get install vim -y
RUN apt-get install less -y
RUN apt-get install jq -y

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

# Jupyter Lab extensions
ENV JUPYTER_ENABLE_LAB true
RUN jupyter serverextension enable --py jupyterlab --sys-prefix
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager @8080labs/qgrid --no-build

#RUN python3 -m pip install jupyterlab-s3-browser
#RUN jupyter labextension install jupyterlab-s3-browser --no-build
#RUN jupyter serverextension enable --py jupyterlab_s3_browser

RUN jupyter lab build

# Container Run
USER root
ADD python-utils/ /opt/python-utils/
ADD transformations/ /opt/transformations/
RUN chmod -R 755 /opt/python-utils/
RUN chmod -R 755 /opt/transformations/

# Bootstrap
ADD bootstrap.sh /etc/jupyterhub/bootstrap.sh

# Necessary to install packages from CodeArtifact
ADD pip.conf /etc/pip.conf
RUN python3 -m pip install --upgrade datamaker-sdk
RUN rm /etc/pip.conf

# should always be the last line of code:
USER $NB_UID