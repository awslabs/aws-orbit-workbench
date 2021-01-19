FROM jupyterhub/jupyterhub:1.3.0

# System packages
RUN apt-get update -y
RUN python3 -m pip install --upgrade pip wheel
RUN python3 -m pip install --upgrade awscli botocore

# Jupyter
ADD jupyterhub_config.py /etc/jupyterhub/jupyterhub_config.py
RUN cat /etc/jupyterhub/jupyterhub_config.py
ADD utils/setup.py /etc/jupyterhub/utils/setup.py
ADD utils/requirements.txt /etc/jupyterhub/utils/requirements.txt
ADD utils/jupyterhub_utils /etc/jupyterhub/utils/jupyterhub_utils
RUN python3 -m pip install -e /etc/jupyterhub/utils/
RUN apt-get install -y vim

# Ports
EXPOSE 8000
EXPOSE 8001
EXPOSE 8081

CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
