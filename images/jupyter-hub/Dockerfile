FROM jupyterhub/jupyterhub:1.2

# System packages
RUN apt-get update -y

# Python packages
RUN python3 -m pip install --upgrade pip wheel
RUN python3 -m pip install --upgrade notebook
RUN python3 -m pip install --upgrade jupyterlab
RUN python3 -m pip install --upgrade jupyterhub-kubespawner
RUN python3 -m pip install --upgrade notebook
RUN python3 -m pip install --upgrade awscli

# Jupyter
RUN jupyter serverextension enable jupyterlab
ENV JUPYTER_ENABLE_LAB true
ADD jupyterhub_config.py /etc/jupyterhub/jupyterhub_config.py
ADD utils/setup.py /etc/jupyterhub/utils/setup.py
ADD utils/requirements.txt /etc/jupyterhub/utils/requirements.txt
ADD utils/jupyterhub_utils /etc/jupyterhub/utils/jupyterhub_utils
RUN python3 -m pip install -e /etc/jupyterhub/utils/

# Ports
EXPOSE 8000
EXPOSE 8001
EXPOSE 8081

CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
