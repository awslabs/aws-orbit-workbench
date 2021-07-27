---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Quick Demo Deployment
permalink: quick-demo-deployment
---


## Pre-deploy

You must have the AWS CLI installed on your system to run our deployment script. 

- For more info, visit https://docs.aws.amazon.com/cli/latest/userguide/welcome-versions.html

## Deploy

Once you have installed the AWS CLI, and is in your environment PATH, the script will do some preliminary work before deploying Orbit

- Check if the AWS CLI is installed
- Check if there are current valid credentials in your shell that will allow interaction with your AWS account
- Create an administrative role for the deployment
- Deploy a Cloudformation template that will create a Codepipeline that deploys Orbit

To get started, download our deployment script:

`curl -LJO https://raw.githubusercontent.com/awslabs/aws-orbit-workbench/main/scripts/orbit_launcher.sh`

Below is the script usage:
```
# ./orbit_launcher.sh -h

usage: script_lancher.sh --orbit-version version --oauth-token github-token [--destroy-pipeline true|false]

  --orbit-version         The version of Orbit to install
  --oauth-token           The GitHub OAuth token that will allow access to pull the Orbit repo
  --branch-override       [OPTIONAL] Overrides the branch that the pipeline pulls from. Default is main
  --destroy-pipeline      [OPTIONAL] Creates a pipeline that destroys the Orbit deployment. Default is false
```

- `--orbit-version` is required. Refer to our [GitHub releases](https://github.com/awslabs/aws-orbit-workbench/releases) for the latest release

- `--oauth-token` is required. You can generate a new token in your [GitHub settings](https://github.com/settings/tokens)



Example:
```
./orbit_launcher.sh --orbit-version 1.0.1 --oauth-token ghp_aaaaabbbbccccc11112222333
```

Once the script completes, it will have deployed a Cloudformation stack to your account that will deploy and trigger a Codepipeline, called 'Orbit_Demo_Deploy', that deploys Orbit.

Note: if you don't specify the `--destroy-pipeline` arg for your itinial deployment, you can always rerun the command above with `--destroy-pipeline` when you want to tear down the environment. It would then update your Cloudformation stack and create a new Codepipeline called 'Orbit_Demo_Destroy'. Codepipeline by default executes pipeline when deployed, so if your initial deployment creates both Codepipelines, you should immediately stop the 'Orbit_Demo_Destroy' pipeline by clicking on 'Stop Execution' on the top right of the main page of your Codepipeline console.

It will take about 1.5-2h to fully deploy the demo. Continue below after the pipeline completes successfully.

## Post Deploy

### Create a user login
- Go to the Cognito console
  - Click on `Manage User Pools`
  - Click on `orbit-demo-fndn-user-pool`
  - Click on `Users and Groups` at the top of the left-hand side menu
  - Click on `Create user`
    - Enter a username
      - Make sure the `Send an invitation to this new user` is checked
      - Uncheck `Make phone number as verified`
      - Enter a valid email address
      - Make sure `Mark email as verified` is checked
        - You should get an email with a temp password within a minute
  - Click on the newly created user
    - Click on the `Add to group` button
      - Add the user to `demo-env-lake-admin`. Click on `Add to group`
      - Add the user to `demo-env-lake-creator`. Click on `Add to group`
      - Add the user to `demo-env-lake-user`. Click on `Add to group`


### Landing Page
- Go to the Systems Manager console
  - Click on `Parameter Store` on the left-hand side menu
  - Click on the parameter called `/orbit/demo-env/context`
  - Search for the `LandingPageUrl` key
    - You should see something like this:
      ```
        "LandingPageUrl": "https://fabd3ce7-istiosystem-istio-2ae2-319103114.us-east-2.elb.amazonaws.com"
      ```
    - Cut and paste that URL in a new tab and append /orbit/login so that the URL looks like this:
      ```
        https://fabd3ce7-istiosystem-istio-2ae2-319103114.us-east-2.elb.amazonaws.com/orbit/login
      ```
- Enter the username you created and the temp password you will have received in your email
  - You will be prompted to change the password. Password requires, uppercase and lowercase letters, numbers, symbols, minimum 8 characters
- Click on the icon to the right of Lake Creator (or any of the users)
  - You will be directed to the Kubeflow dashboard

### Accessing Notebook Servers
- Navigate to the left-side menu and click on `Notebook Servers` 
- Click on `New Server` at the top right
  - In the `Name` field, give your server a recognizable name
  - Feel free to change any settings on this page, but to get started quickly, we will just start the server
  - Select `Launch` at the bottom

## Demo notebooks execution

- Navigate to demo notebook
  - Path: /shared/samples/notebooks/Z-Tests/demo-lake-creator-notebook.ipynb
- Execute all the cells sequentially to trigger the lake-creator notebooks.
