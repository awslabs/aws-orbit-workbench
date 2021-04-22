FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/python:3.8.7-slim-buster

# RUN apt -y update && \
#     # Install dependencies
#     apt -y install curl unzip wget && \
#     # Install AWSCLIv2
#     curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
#     unzip awscliv2.zip && \
#     ./aws/install

RUN mkdir -p /var/image-replicator

COPY src/* /var/image-replicator/

RUN python3 /var/image-replicator/setup.py install

# ENTRYPOINT ["image-replicator"]
ENTRYPOINT ["bash"]