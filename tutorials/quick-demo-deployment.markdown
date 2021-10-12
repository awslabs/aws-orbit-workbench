---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Quick Demo Deployment
permalink: quick-demo-deployment
---


We have provided a `one-click deployment` that will install most features of the AWS Orbit Workbench in a trial environment in your AWS account.  If you are just evaluating the workbench, 
we suggest you use this deployment.  

You can always use the [CLI](cli-guide) to redeploy to add / remove teams or plugins to an existing workbench.

## Pre-deploy

You should have the AWS CLI installed on your system to run our deployment script (after the initial one-click deployment).

- For more info, visit https://docs.aws.amazon.com/cli/latest/userguide/welcome-versions.html

## Deploy

Please see our <a href="https://github.com/awslabs/aws-orbit-workbench"> AWS Orbit Workbench Github repository.</a>  The landing page has the `one-click deployment` for your
particular region.

It will take about 1.5-2h to fully deploy the demo. Continue below after the pipeline completes successfully.

## Post Deploy

There will be an `orbit` user created with credentials as described on the Github site.  You can add additional users as denoted below.
### Create a user login
- Go to the Cognito console
  - Click on `Manage User Pools`
  - Click on `orbit-fdn-user-pool`
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
      - Add the user to `trial-lake-admin`. Click on `Add to group`
      - Add the user to `trial-lake-creator`. Click on `Add to group`
      - Add the user to `trial-lake-user`. Click on `Add to group`


### Landing Page
- Go to the Systems Manager console
  - Click on `Parameter Store` on the left-hand side menu
  - Click on the parameter called `/orbit/trial/context`
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
