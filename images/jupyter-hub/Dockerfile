FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyterhub/jupyterhub:1.3.0

# System packages
RUN apt-get -y update && \
    apt-get install --no-install-recommends -y \
    vim && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip wheel awscli botocore voila

# JupyterHub Utils
ADD utils/setup.py /etc/jupyterhub/utils/setup.py
ADD utils/requirements.txt /etc/jupyterhub/utils/requirements.txt
ADD utils/jupyterhub_utils /etc/jupyterhub/utils/jupyterhub_utils
RUN python3 -m pip install -e /etc/jupyterhub/utils/
ADD utils/orbit.svg /etc/jupyterhub/orbit.svg

# Ports
EXPOSE 8000
EXPOSE 8001
EXPOSE 8081

CMD ["jupyterhub", "-f", "/config/jupyterhub_config.py"]
