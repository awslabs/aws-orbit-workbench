FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/python:3.8.7-slim-buster

RUN mkdir -p /var/image-replicator

ADD src /var/image-replicator/

RUN cd /var/image-replicator/ && \
    pip3 install -e .

WORKDIR /var/image-replicator
ENTRYPOINT ["image-replicator"]
