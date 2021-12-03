ARG BASE_IMAGE=1234567890.dkr.ecr.us-west-2.amazonaws.com/orbit/k8s-utilities:base
FROM $BASE_IMAGE


COPY src/requirements.txt /
RUN pip install -r /requirements.txt

RUN mkdir -p /var/orbit-controller
ADD src /var/orbit-controller/
ADD image_inventory.txt /var/orbit-controller/image_inventory.txt

RUN cd /var/orbit-controller/ && \
    pip3 install -e .

# RUN pip uninstall jwt==1.0.0 && pip uninstall PyJWT && pip install PyJWT~=2.1.0

WORKDIR /var/orbit-controller/

CMD ["bash"]
