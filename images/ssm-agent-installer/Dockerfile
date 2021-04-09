FROM public.ecr.aws/v3o4w1g6/jicowan/ssm-agent-installer:1.2

RUN mkdir /rpmtmp/
RUN apt-get update \
    && apt-get install -y wget \
    && rm -rf /var/lib/apt/lists/* \
    && wget -O /rpmtmp/amazon-ssm-agent.rpm https://s3.us-east-1.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/linux_amd64/amazon-ssm-agent.rpm

COPY runonhost.sh /
RUN chmod u+x runonhost.sh
CMD ["./runonhost.sh"]