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

# Okta Integration Guide

## 1 - Preparing Cognito User Pool

* Open the Cognito User Pool console: `https://console.aws.amazon.com/cognito/users/`
* Select your User Pool (`orbit-{YOUR_ENV_NAME}`)
* In the left pane click in `General settings` > `Attributes`
* In the page botton click in `Add another attribute` and then save it.

![Custom Teams Attribute](_static/okta/create-teams-attribute.png?raw=true "Custom Teams Attribute")

* In the left pane click in `App integration` > `Domain name`
* Add any valid custom domain name

![Domain Name](_static/okta/domain-name.png?raw=true "Domain Name")

## 2 - Creating an Okta account

> _If you already have an Okta developer account, sign in and skip this topic._

* On the [Okta Developer signup webpage](https://developer.okta.com/signup/), enter the required information, and then choose GET STARTED. The Okta Developer Team sends a verification email to the email address that you provided.
* In the verification email, find the sign-in information for your account. Choose ACTIVATE MY ACCOUNT, sign in, and finish creating your account.

## 3 - Configuring the Okta application

* Open the Okta Developer Console. For more information about the console, see [The Okta Developer Console: All new, All you](https://developer.okta.com/blog/2017/09/25/all-new-developer-console) on the Okta Developer Blog.
* In the top left corner, pause on Developer Console, and then choose Classic UI. This opens the Admin Console. For more information, see [Administrator Console](https://developer.okta.com/docs/concepts/okta-organizations/#administrator-console) on the Okta Organizations page of the Okta Developer website.

> _Important: You must be in the Admin Console (Classic UI) to create a SAML app._

* Choose Applications, and then choose Add Application.
* On the Add Application page, choose Create New App.
* In the Create a New Application Integration dialog, confirm that Platform is set to Web.
* For Sign on method, choose SAML 2.0.
* Choose Create.

> _For more information, see [Prepare your integration](https://developer.okta.com/docs/guides/build-sso-integration/saml2/before-you-begin/) in the Build a Single Sign-On (SSO) Integration guide on the Okta Developer website._

* On the Create SAML Integration page, under General Settings, enter a name for your app. (e.g. orbit-my-env)
* (Optional) Upload the [Orbit Workbench logo](https://github.com/awslabs/aws-eks-data-maker/blob/main/images/landing-page/public/orbit1.png) and choose the visibility settings for your app.
* Choose Next.
* Under **GENERAL**, for **Single sign on URL**, enter `https://yourDomainPrefix.auth.region.amazoncognito.com/saml2/idpresponse`.

> _Replace yourDomainPrefix and region with the values for your user pool. You can find these values in the Amazon Cognito console on the Domain name page for your user pool._

* For **Audience URI (SP Entity ID)**, enter `urn:amazon:cognito:sp:yourUserPoolId`.

> _Replace yourUserPoolId with your Amazon Cognito user pool ID. You can find this value in the Amazon Cognito console on the General settings page for your user pool._

* Under **ATTRIBUTE STATEMENTS (OPTIONAL)**, add a statement with the following information:
  * For **Name**, enter the SAML attribute name `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`.
  * For **Value**, enter `user.email`.
* Under **GROUP ATTRIBUTE STATEMENTS (OPTIONAL)**, add a statement with the following information:
  * For **Name**, enter the SAML attribute name `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/teams`.
  * For **Filter** select `Matches regex`.
  * For **Value**, enter `.*`.

![Okta App Attributes](_static/okta/okta-app-attributes.png?raw=true "Okta App Attributes")

* For all other settings on the page, leave them as their default values or set them according to your preferences.
* Choose Next.
* Choose a feedback response for Okta Support.
* Choose Finish.

> _For more information, see [Create your integration](https://developer.okta.com/docs/guides/build-sso-integration/saml2/create-your-app/) in the Build a Single Sign-On (SSO) Integration guide on the Okta Developer website._

## 4 - Assign a user to your Okta application

* On the Assignments tab for your Okta app, for Assign, choose Assign to People.
* Choose Assign next to the user that you want to assign.

> _If this is a new account, the only option available is to choose yourself (the admin) as the user._

* (Optional) For User Name, enter a user name, or leave it as the user's email address, if you want.
* Choose Save and Go Back. Your user is assigned.
* Choose Done.

> _For more information, see [Assign users](https://developer.okta.com/docs/guides/build-sso-integration/saml2/test-your-app/#assign-users) in the Build a Single Sign-On (SSO) Integration guide on the Okta Developer website._

## 5 - Get the IdP metadata for your Okta application

* On the **Sign On** tab for your Okta app, find the **Identity Provider metadata** hyperlink. Right-click the hyperlink, and then copy the URL.

> _For more information, see [Specify your integration settings](https://developer.okta.com/docs/guides/build-sso-integration/saml2/specify-your-settings/) in the Build a Single Sign-On (SSO) Integration guide on the Okta Developer website._

## 6 - Configuring Cognito User Pool - Identity Provider

* Open the Cognito User Pool console: `https://console.aws.amazon.com/cognito/users/`
* Select your User Pool (`orbit-{YOUR_ENV_NAME}`)
* In the left navigation pane, under **Federation**, choose **Identity providers**.
* Choose SAML.
* Under **Metadata document**, paste the **Identity Provider metadata** URL that you copied.
* For Provider name, enter `okta`. For more information, see [Choosing SAML Identity Provider Names](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managing-saml-idp-naming.html).
* (Optional) Enter any SAML identifiers (Identifiers (Optional)) and enable sign-out from the IdP (Okta) when your users sign out from your user pool (Enable IdP sign out flow).
* Choose Create provider.

> _For more information, see [Creating and managing a SAML identity provider for a user pool (AWS Management Console)](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managing-saml-idp-console.html)._

## 7 - Configuring Cognito User Pool - Attributes Mapping

* In the left navigation pane, under Federation, choose Attribute mapping.
* On the attribute mapping page, choose the SAML tab.
* Choose Add SAML attribute.
* Map the e-mail attributes
  * For **SAML attribute**, enter the SAML attribute name `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`.
  * For **User** pool attribute, choose `Email` from the list.
* Map the teams attributes
  * For **SAML attribute**, enter the SAML attribute name `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/teams`.
  * For **User** pool attribute, choose `custom:teams` from the list.

![Mapped Attributes](_static/okta/mapped-attributes.png?raw=true "Mapped Attributes")

> _For more information, see [Specifying identity provider attribute mappings for your user pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-specifying-attribute-mapping.html)._

## 8 - Configuring Cognito User Pool - Client Settings

* In the left navigation pane, under **App integration**, choose **App client settings**.
* On the app client page, do the following:
Under Enabled Identity Providers, select the Okta and Cognito User Pool check boxes.
* For Callback URL(s), enter a URL where you want your users to be redirected after they log in. Enter your Orbit Workbench URL.
* For Sign out URL(s), enter a URL where you want your users to be redirected after they log out.  Enter your Orbit Workbench URL.
* Under Allowed OAuth Flows, be sure to select at least the Implicit grant check box.
* Under Allowed OAuth Scopes, be sure to select at least the email and openid check boxes.
* Choose Save changes.

> _For more information, see [App client settings overview](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-app-idp-settings.html#cognito-user-pools-app-idp-settings-about)._

![Client Settings](_static/okta/client-settings.png?raw=true "Client Settings")

## 8 - Configuring the Orbit Workbench manifest file (YAML)

* Add two new attributes in the root level:

```yaml
external-idp: okta
external-idp-label: OKTA
```

* Deploy:

`datamaket deploy_env_and_teams -f YOUR_FILE.yaml`

![Landing Page](_static/okta/landing-page.png?raw=true "Landing Page")

---

## Extra Resources

* [https://aws.amazon.com/premiumsupport/knowledge-center/cognito-okta-saml-identity-provider/](https://aws.amazon.com/premiumsupport/knowledge-center/cognito-okta-saml-identity-provider/)