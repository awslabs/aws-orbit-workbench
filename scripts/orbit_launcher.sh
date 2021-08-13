#!/bin/bash

usage(){
    echo ""
    echo "usage: `basename $0` --orbit-version version --oauth-token github-token [--destroy-pipeline true|false --internet-accessibility true|false]"
    echo ""
    echo "  --orbit-version             The version of Orbit to install"
    echo "  --oauth-token               The GitHub OAuth token that will access the Orbit repo"
    echo "  --internet-accessibility    [OPTIONAL] Determines if internet will be accessible for the deployment. Default is true"
    echo "  --branch-override           [OPTIONAL] Overrides the branch that the pipeline pulls from. Default is main"
    echo "  --destroy-pipeline          [OPTIONAL] Creates a pipeline that destroys the Orbit deployment. Default is false"
    echo "  -h, --help                  Display help"
    echo ""
    exit 1
    
}

if [[ $1 == "-h" ]] || [[ $1 == "--help" ]] || $# -eq 0 ]]; then
    usage
fi

if ! aws --version &> /dev/null; then
    echo "Please install the AWS Cli. More information can be found here: https://docs.aws.amazon.com/cli/latest/userguide/welcome-versions.html"
    exit 1
else
    echo "Checking AWS credentials..."

    CRED_STATUS=`aws sts get-caller-identity --no-cli-pager &> /dev/null`
    if [[ $? -ne 0 ]]; then
        echo "An error occurred (InvalidClientTokenId): The security token included in the request is invalid or has expired."
        exit 1
    fi
fi

while [[ $# -gt 0 ]]; do
    case $1 in 
        --orbit-version)
            ORBIT_VERSION=$2
            shift
            ;;
        --branch-override)
            BRANCH_OVERRIDE=$2
            shift
            ;;
        --oauth-token)
            OAUTH_TOKEN=$2
            shift
            ;;
        --internet-accessibility)
            INTERNET_ACCESSIBILITY=$2
            shift
            ;;
        --destroy-pipeline)
            DESTROY_PIPELINE=$2
            shift
            ;;
    esac
    shift
done

if [[ -z "${ORBIT_VERSION}" ]]; then
    echo "Please specify an Orbit version"
    usage
fi

if [[ -z "${OAUTH_TOKEN}" ]]; then
    echo "Please provide a GitHub OAuth token"
    usage
fi

if [[ -z "${BRANCH_OVERRIDE}" ]]; then
    BRANCH_OVERRIDE="main"
fi

if [[ -z "${INTERNET_ACCESSIBILITY}" ]]; then
    INTERNET_ACCESSIBILITY="true"
fi

if [[ -z "${DESTROY_PIPELINE}" ]]; then
    DESTROY_PIPELINE="false"
fi

ORBIT_ADMIN_ROLE="OrbitAdmin"
ASSUME_ROLE='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

if ! aws iam list-roles --no-cli-pager | grep -i "\"RoleName\": \"${ORBIT_ADMIN_ROLE}\"" &> /dev/null; then
    echo "Creating role ${ORBIT_ADMIN_ROLE}"

    CREATE_ROLE_RESP=`aws iam create-role --role-name "${ORBIT_ADMIN_ROLE}" --assume-role-policy-document "${ASSUME_ROLE}" --no-cli-pager`

    if [[ $? -ne 0 ]];  then
        echo 'There was an issue creating the IAM Role'
        echo "${CREATE_ROLE_RESP}"
        exit 1
    fi

    echo "Attaching Administrative policy to ${ORBIT_ADMIN_ROLE}"

    ATTACH_POLICY_TO_ROLE_RESP=`aws iam attach-role-policy --role-name "${ORBIT_ADMIN_ROLE}" --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" --no-cli-pager`
    if [[ $? -ne 0 ]];  then
        echo 'There was an issue attaching the Administrator policy to the IAM Role'
        echo "${ATTACH_POLICY_TO_ROLE_RESP}"
        exit 1
    fi

    echo "Administrative role ${ORBIT_ADMIN_ROLE} has been created."
fi

echo "Downloading the cloudfromation template that deploys Orbit..."
curl -LJO https://raw.githubusercontent.com/awslabs/aws-orbit-workbench/main/demo_pipeline.yaml

ORBIT_ENV_NAME="demo-env"

aws cloudformation deploy \
    --template-file demo_pipeline.yaml \
    --stack-name orbit-demo \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        Branch="${BRANCH_OVERRIDE}" \
        EnvName="${ORBIT_ENV_NAME}" \
        Version="${ORBIT_VERSION}" \
        K8AdminRole="${ORBIT_ADMIN_ROLE}" \
        GitHubOAuthToken="${OAUTH_TOKEN}" \
        DestroyPipeline="${DESTROY_PIPELINE}" \
        IsInternetAccessible="${INTERNET_ACCESSIBILITY}"
