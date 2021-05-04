FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/python:3.8.7-slim-buster

RUN mkdir -p /var/admission-controller

ADD src /var/admission-controller/

RUN cd /var/admission-controller/ && \
    pip3 install .

WORKDIR /var/admission-controller/
ENTRYPOINT ["gunicorn"]
CMD ["aws_orbit_admission_controller.app:app"]
