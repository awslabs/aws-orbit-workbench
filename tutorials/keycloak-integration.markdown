---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: KeyCloak Integration
permalink: keycloak-integration
---

<!--
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#   
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#   
#        http://www.apache.org/licenses/LICENSE-2.0
#   
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
-->

## Useful Links

* [KeyCloak Documenation Site](https://www.keycloak.org/documentation)


## 1 - Preparing Cognito User Pool

* Open the Cognito User Pool console: `https://console.aws.amazon.com/cognito/users/`
* Select your User Pool (`orbit-{YOUR_ENV_NAME}`)
* In the left navigation pane, under `General settings`, get the **Pool Id** of the User Pool and save it for later
* In the left pane, click on `General settings` > `Attributes`
* In the page botton click on `Add custom attribute` and then save it.

<img src="./img/integrations/user-pool-custom-attribute.png" alt="User Pool Attribute"/>


* In the left pane, click on `App integration` > `Domain name`
* Add any valid domain name

![Domain Name](https://github.com/awslabs/aws-orbit-workbench/blob/main/docs/_static/okta/domain-name.png?raw=true "Domain Name")

## 2 - Create a KeyCloak Server

> _If you already have a KeyCloak implementation, sign in and skip this topic._

* You create a KeyCloak server on AWS.  Please refer to [KeyCloak on AWS](https://github.com/aws-samples/keycloak-on-aws)

## 3 - Configuring the KeyCloak Server


* Select the `REALM` you'd like to use, or create a new one
* On `Clients` -> `Create` upload the [AWS SAML Metadata File](https://signin.aws.amazon.com/static/saml-metadata.xml)  
* Once resolved, edit the Client Id
  * REMOVE: **`urn:amazon:webservices`**
  * ADD: **`urn:amazon:cognito:sp:us-west-2_xxxxxxxxx`**  (Replace xxxxxxxxx with the UserPoolId you got above)
* Click `Create` <br/>
<img src="img/integrations/keycloak-client-create.png"/>
<br/>
<br/>

* Edit the following properties:
  * Client Signature Required – **TURN OFF**
  * Name ID Format - **username**
  * Valid Redirect URI’s – change to wildcard **`*`**
  * Base URL: change to **/auth/realms/{realm}/protocol/saml/clients/amazon-aws**  (replace realm with your realm)
  * IDP Initiated SSO URL Name: change to **amazon-aws** <br/>
<img src="img/integrations/keycloak-client-configs.png"/>
<br/>
<br/>

* The following mappings need to be set up:
  * **email_verified** – confirm that the email address is verified (all emailaddress MUST be verified in KeyCloak)
  * **emailaddress** – email address of logged in user
  * **group** – represents the ROLES that the user is assigned to
    * be sure to mark the Single Role Attribute as **ON**<br/>
<img src="img/integrations/keycloak-email-verified.png"/>
<br/> 
<img src="img/integrations/keycloak-emailaddress.png"/>
<br/> 
<img src="img/integrations/keycloak-groups.png"/>
<br/>



## 4 - Get the IdP metadata for your KeyCloak realm

Fetch the `SAML-Metadata-IDPSSODescriptor.xml` file from your KeyCloak Server
 
* Typically, it can be found at 
`https://{keycloak-server}/auth/realms/{realm}/protocol/saml/descriptor` (change the DNS of your server and the realm)

## 5 - Configuring Cognito User Pool - Identity Provider

* Open the Cognito User Pool console: `https://console.aws.amazon.com/cognito/users/`
* Select your User Pool (`orbit-{YOUR_ENV_NAME}`)
* In the left navigation pane, under **Federation**, choose **Identity providers**.
* Choose SAML.
* Under **Metadata document**, paste the **Identity Provider metadata** URL that you copied.
* For Provider name, enter `keycloak`. For more information, see [Choosing SAML Identity Provider Names](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managing-saml-idp-naming.html).
* (Optional) Enter any SAML identifiers (Identifiers (Optional)) and enable sign-out from the IdP (Keycloak) when your users sign out from your user pool (Enable IdP sign out flow).
* Choose Create provider.

> _For more information, see [Creating and managing a SAML identity provider for a user pool (AWS Management Console)](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managing-saml-idp-console.html)._

## 7 - Configuring Cognito User Pool - Attributes Mapping

* In the left navigation pane, under Federation, choose Attribute mapping.
* On the attribute mapping page, choose the SAML tab.
* Choose Add SAML attribute.
* Map the groups attributes
  * For **SAML attribute**, enter the SAML attribute name `groups`.
  * For **User** pool attribute, choose `custom:groups` from the list.
* Map the e-mail attributes
  * For **SAML attribute**, enter the SAML attribute name `emailaddress`.
  * For **User** pool attribute, choose `Email` from the list.
* Map the email_verified attributes
  * For **SAML attribute**, enter the SAML attribute name `email_verified`.
  * For **User** pool attribute, choose `Email Verified` from the list.
* Map the username attributes
  * For **SAML attribute**, enter the SAML attribute name `username`.
  * For **User** pool attribute, choose `Preferred User Name` from the list.

<img src="img/integrations/cognito-attr-mappings.png" alt="KeyCloak Mappings"/>

> _For more information, see [Specifying identity provider attribute mappings for your user pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-specifying-attribute-mapping.html)._

* Save Changes

## 8 - Get the Orbit Workbench URL
* Open the Systems Manager Console
  * On the left, select `Parameter Store`
  * Select /orbit/`{your-env-name}`/context
  * Search for LandingPageUrl, you will need it below

## 9 - Configuring Cognito User Pool - Client Settings

* In the left navigation pane, under **General settings**, get the `Pool Id` of the User Pool


## 10 - Configuring the Orbit Workbench manifest file (YAML)

* Add these new attributes in the root level, and fill in `CognitoExternalProviderDomain` and `CognitoExternalProviderRedirect` with your configurations:

```yaml
UserPoolId: us-west-X_xXXXxxXXx
CognitoExternalProvider: keycloak
CognitoExternalProviderLabel: KEYCLOAK
# The domain created in Coginto
CognitoExternalProviderDomain: domain.auth.region.amazoncognito.com
# The Orbit Workbench URL
CognitoExternalProviderRedirect: https://a12389bc893fa0980ce08f1000ecf89a.region.elb.amazonaws.com/orbit/login
```

* Deploy:

`orbit deploy env -f YOUR_FILE.yaml`

You should see a 'Sign in with Keycloak' button on the landing page


## 11 - Sign in
* Go back to your landing page and click on `Sign in with Keycloak`
  * You will be prompted to login with with your Keycloak account
  * You should see the Lake Admin, Lake Creator and Lake User groups after you sign in