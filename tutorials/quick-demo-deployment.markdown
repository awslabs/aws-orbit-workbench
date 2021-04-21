---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: tutorial
title: Quick Demo Deployment
permalink: quick-demo-deployment
---

## Deploy the demo pipeline

- Create an Admin role
  - In IAM, create a new role.
  - On the 'Select type of trusted entity' page, select `Codebuild`.
  - On the 'Permissions' page, select `AdministrativeAccess`
  - Give the role a name, it will be mapped below to the K8AdminRole parameter

- Get the cloudformation for the pipeline:

`curl -LJO https://raw.githubusercontent.com/awslabs/aws-orbit-workbench/main/demo_pipeline.yaml -o demo_pipeline.yaml`

- Deploy the pipeline

`aws cloudformation deploy --template-file demo_pipeline.yaml --stack-name orbit-demo --capabilities CAPABILITY_IAM --parameter-overrides Branch=main EnvName=demo-env Version=<orbit version> K8AdminRole=<admin role name> GitHubOAuthToken=<your oauth token>`

e.g.,
`aws cloudformation deploy --template-file demo_pipeline.yaml --stack-name orbit-demo --capabilities CAPABILITY_IAM --parameter-overrides Branch=main EnvName=demo-env Version=0.14.2 K8AdminRole=Admin GitHubOAuthToken=ghp_Vxxxxxxxxxx`


Once the cloudformation completes, the code pipeline names 'Orbit_Demo_Deploy' will start running (and the 'Orbit_Demo_Destroy' will fail and thats ok. If it doesn't fail, click the 'Orbit_Demo_Destroy' and click on 'Stop Execution' on the top right).

It will take 1-2h to fully deploy the demo. Continue below after the pipeline completes successfully.

## Create a login user
### Go to the Cognito console
- Click on `Manage User Pools`
- Click on `orbit-dev-fndn-user-pool`
- Click on `Users and Groups` at the top of the left-hand side menu
- Click on `Create user`
  - Enter a username e.g. `orbit`
    - Make sure the `Send an invitation to this new user` is checked
    - Uncheck `Make phone number as verified`
    - Enter a valid email address
    - Make sure `Mark email as verified` is checked
      - You should get an email with a temp password within a minute
- Click on the newly created user
  - Click on the `Add to group` button
    - Add the user to `lake-creator`. Click on `Add to group`
    - Add the user to `lake-user`. Click on `Add to group`

## Landing Page
### Go to the Systems Manager console
- Click on `Parameter Store` on the left-hand side menu
- Click on the parameter called `/orbit/demo-env/context`
- Search for the `LandingPageUrl` key
  - You should see something like this:
  ```
    "LandingPageUrl": "http://aea06eb3c2bab312ff3429f329e30bf-423423421.us-east-1.elb.amazonaws.com"
  ```
  - Open the link
  - Enter the username you created and the temp password you will have received in your email
    - You will be prompted to change the password. Password requires, uppercase and lowercase letters, numbers, symbols, minimum 8 characters
  - Click on the icon to the right of Lake Creator
  - Click on `Start My Server`

## Demo notebooks execution
- Navigate to demo notebook. Path - /shared/samples/notebooks/Z-Tests/demo-notebook.ipynb
- Execute all the cells sequentially to trigger the lake-creator, admin and lake-user notebooks.
