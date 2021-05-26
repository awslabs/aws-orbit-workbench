FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/k8s-utilities:1.0.0

RUN mkdir -p /var/admission-controller

ADD src /var/admission-controller/

RUN cd /var/admission-controller/ && \
    pip3 install -e .

RUN pip3 install Flask-Cognito

WORKDIR /var/admission-controller/
CMD ["bash"]
