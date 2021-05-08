FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/python:3.8.7-slim-buster

# This makes it easy to build tagged images with different `kubectl` versions.
ARG KUBECTL_VERSION="v1.19.2"

# Set by docker automatically
ARG TARGETOS
ARG TARGETARCH

RUN apt -y update && \
    # ---- Install CLIs ----
    apt -y install \
    curl \
    unzip \
    wget \
    git \
    zip \
    less \
    jq \
    openssl \
    vim-tiny \
    nano-tiny \
    # ---- Clean up ----
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/nano nano /bin/nano-tiny 10 && \
    # ---- Install AWS CLI ----
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    # ---- Install kubectl CLI ----
    wget "https://storage.googleapis.com/kubernetes-release/release/${KUBECTL_VERSION}/bin/${TARGETOS}/${TARGETARCH}/kubectl" && \
    chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl && \
    # ---- Install helm CLI ----
    curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash && \
    helm plugin install https://github.com/hypnoglow/helm-s3.git && \
    helm repo add stable https://charts.helm.sh/stable && \
    # ---- Install aws-iam-authenticator ----
    curl -o aws-iam-authenticator https://amazon-eks.s3.us-west-2.amazonaws.com/1.19.6/2021-01-05/bin/linux/amd64/aws-iam-authenticator && \
    chmod +x ./aws-iam-authenticator && \
    mv ./aws-iam-authenticator /usr/local/bin


ENTRYPOINT [ "bash" ]
