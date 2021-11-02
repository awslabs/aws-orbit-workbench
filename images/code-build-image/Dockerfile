# Copyright 2020-2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#    http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file.
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied.
# See the License for the specific language governing permissions and limitations under the License.

FROM public.ecr.aws/ubuntu/ubuntu:20.04 AS core

ARG DEBIAN_FRONTEND="noninteractive"
ARG BOTO_VERSION=1.18.0
ARG CDK_VERSION=1.100.0

# Install git, SSH, and other utilities
RUN set -ex \
    && echo 'Acquire::CompressionTypes::Order:: "gz";' > /etc/apt/apt.conf.d/99use-gzip-compression \
    && apt-get update \
    && apt install -y -qq apt-transport-https gnupg ca-certificates \
    && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 3FA7E0328081BFF6A14DA29AA6A19B38D3D831EF \
    && apt-get install software-properties-common -y -qq --no-install-recommends \
    && apt-add-repository -y ppa:git-core/ppa \
    && apt-get update \
    && apt-get install git=1:2.* -y -qq --no-install-recommends \
    && git version \
    && apt-get install -y -qq --no-install-recommends openssh-client \
    && mkdir ~/.ssh \
    && touch ~/.ssh/known_hosts \
    && ssh-keyscan -t rsa,dsa -H github.com >> ~/.ssh/known_hosts \
    && ssh-keyscan -t rsa,dsa -H bitbucket.org >> ~/.ssh/known_hosts \
    && chmod 600 ~/.ssh/known_hosts \
    && apt-get install -y -qq --no-install-recommends \
        apt-utils autoconf automake build-essential bzip2 bzr curl dirmngr dpkg-dev \
        e2fsprogs expect fakeroot file g++ gcc  groff gzip iptables jq less \
        libc6-dev libcurl4-openssl-dev  libkrb5-dev liblzma-dev libmagickcore-dev \
        libmagickwand-dev  libmysqlclient-dev libonig-dev  libserf-1-1 libsqlite3-dev libssl-dev \
        libtcl8.6  llvm locales make mlocate  netbase openssl patch pkg-config python3-configobj \
        python-openssl rsync stunnel tar tcl tcl8.6 tk tk-dev unzip wget xfsprogs xml-core xmlto \ 
        xsltproc libzip5 libzip-dev vim xvfb xz-utils zip zlib1g-dev pigz \
    && rm -rf /var/lib/apt/lists/*

ENV LC_CTYPE="C.UTF-8"

RUN useradd codebuild-user

#=======================End of layer: core  =================


FROM core AS tools

RUN curl -sL https://deb.nodesource.com/setup_12.x | bash - && \
    apt-get -y install nodejs

### AWS Tools

# Install EKSCTL
RUN curl --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp && \
    mv /tmp/eksctl /usr/local/bin

# Install KubeCTL
RUN curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl

# Install aws-iam-authenticator
# https://docs.aws.amazon.com/eks/latest/userguide/install-aws-iam-authenticator.html 
RUN curl -o aws-iam-authenticator https://amazon-eks.s3.us-west-2.amazonaws.com/1.19.6/2021-01-05/bin/linux/amd64/aws-iam-authenticator && \
    chmod +x ./aws-iam-authenticator && \
    mv ./aws-iam-authenticator /usr/local/bin

# Install KFCTL
RUN wget -O kfctl_v1.2.0-0_linux.tar.gz https://github.com/kubeflow/kfctl/releases/download/v1.2.0/kfctl_v1.2.0-0-gbc038f9_linux.tar.gz && \
    tar xzf kfctl_v1.2.0-0_linux.tar.gz && \
    chmod +x kfctl && \
    mv kfctl /usr/local/bin

# Install Helm tools
RUN curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash && \
    helm version --short && \
    helm plugin install https://github.com/hypnoglow/helm-s3.git && \
    helm repo add stable https://charts.helm.sh/stable

RUN npm install -g aws-cdk@$CDK_VERSION yarn

# Install AWS CLI v2
# https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-linux.html
RUN curl https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /opt \
    && /opt/aws/install -i /usr/local/aws-cli -b /usr/local/bin \
    && rm /tmp/awscliv2.zip \
    && rm -rf /opt/aws \
    && aws --version

#python
RUN curl https://pyenv.run | bash
ENV PATH="/root/.pyenv/shims:/root/.pyenv/bin:$PATH"

#=======================End of layer: tools  =================
FROM tools AS runtimes


#**************** PYTHON *****************************************************
ENV PYTHON_37_VERSION="3.7.10"
ARG PYTHON_PIP_VERSION=21.1.2
ENV PYYAML_VERSION=5.4.1

COPY tools/runtime_configs/python/$PYTHON_37_VERSION /root/.pyenv/plugins/python-build/share/python-build/$PYTHON_37_VERSION
RUN   env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install $PYTHON_37_VERSION; rm -rf /tmp/*
RUN   pyenv global  $PYTHON_37_VERSION
RUN set -ex \
    && pip3 install --no-cache-dir --upgrade --force-reinstall "pip==$PYTHON_PIP_VERSION" \
    && pip3 install --no-cache-dir --upgrade "PyYAML==$PYYAML_VERSION" \
    && pip3 install --no-cache-dir --upgrade 'setuptools==57.4.0' wheel aws-sam-cli pipenv virtualenv --use-feature=2020-resolver

#**************** END PYTHON *****************************************************


#=======================End of layer: runtimes  =================


RUN pip install boto3~=$BOTO_VERSION \
                aws_cdk.core~=$CDK_VERSION \
                aws-cdk.aws-codecommit~=$CDK_VERSION \
                aws-cdk.aws-ec2~=$CDK_VERSION \
                aws-cdk.aws-s3~=$CDK_VERSION \
                aws-cdk.aws-iam~=$CDK_VERSION \
                aws-cdk.aws-efs~=$CDK_VERSION \
                aws-cdk.aws-ecr~=$CDK_VERSION \
                aws-cdk.aws-ecs~=$CDK_VERSION \
                aws-cdk.aws-events~=$CDK_VERSION \
                aws-cdk.aws-events-targets~=$CDK_VERSION \
                aws-cdk.aws-ssm~=$CDK_VERSION \
                aws-cdk.aws-kms~=$CDK_VERSION \
                aws-cdk.aws-cognito~=$CDK_VERSION \
                aws-cdk.aws-lambda~=$CDK_VERSION \
                aws-cdk.aws-lambda-python~=$CDK_VERSION \
                aws-cdk.aws-redshift~=$CDK_VERSION \
                aws-cdk.aws-sns~=$CDK_VERSION \
                aws-cdk.aws-sns-subscriptions~=$CDK_VERSION \
                aws-cdk.aws-stepfunctions~=$CDK_VERSION \
                aws-cdk.aws-stepfunctions-tasks~=$CDK_VERSION \
                aws-cdk.aws-codeartifact~=$CDK_VERSION

#****************        DOCKER    *********************************************
ARG DOCKER_BUCKET="download.docker.com"
ARG DOCKER_CHANNEL="stable"
ARG DIND_COMMIT="3b5fac462d21ca164b3778647420016315289034"
ARG DOCKER_COMPOSE_VERSION="1.27.4"
ARG SRC_DIR="/usr/src"

ARG DOCKER_SHA256="caf74e54b58c0b38bb4d96c8f87665f29b684371c9a325562a3904b8c389995e"
ARG DOCKER_VERSION="20.10.9"

# Install Docker
RUN set -ex \
    && curl -fSL "https://${DOCKER_BUCKET}/linux/static/${DOCKER_CHANNEL}/x86_64/docker-${DOCKER_VERSION}.tgz" -o docker.tgz \
    && echo "${DOCKER_SHA256} *docker.tgz" | sha256sum -c - \
    && tar --extract --file docker.tgz --strip-components 1  --directory /usr/local/bin/ \
    && rm docker.tgz \
    && docker -v \
    # set up subuid/subgid so that "--userns-remap=default" works out-of-the-box
    && addgroup dockremap \
    && useradd -g dockremap dockremap \
    && echo 'dockremap:165536:65536' >> /etc/subuid \
    && echo 'dockremap:165536:65536' >> /etc/subgid \
    && wget -q "https://raw.githubusercontent.com/docker/docker/${DIND_COMMIT}/hack/dind" -O /usr/local/bin/dind \
    && curl -L https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-Linux-x86_64 > /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/dind /usr/local/bin/docker-compose \
    # Ensure docker-compose works
    && docker-compose version

VOLUME /var/lib/docker
#*********************** END  DOCKER  ****************************

# Activate runtime versions specific to image version.
RUN pyenv  global $PYTHON_37_VERSION

RUN mkdir -p /var/scripts/
ADD retrieve_docker_creds.py /var/scripts/retrieve_docker_creds.py

COPY dockerd-entrypoint.sh /usr/local/bin/

#ENTRYPOINT ["dockerd-entrypoint.sh"]
ENTRYPOINT ["bash"]
#=======================END of STD:5.0  =================
