/*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 *   Licensed under the Apache License, Version 2.0 (the "License").
 *   You may not use this file except in compliance with the License.
 *   You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 *   Unless required by applicable law or agreed to in writing, software
 *   distributed under the License is distributed on an "AS IS" BASIS,
 *   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *   See the License for the specific language governing permissions and
 *   limitations under the License.
 */

import Amplify from "aws-amplify";
import "./App.css";
import "antd/dist/antd.css";
import Frame from "./components/frame";
import Teams from "./components/teams";
import { SignIn, SignInExternal } from "./components/signin";
import { useAuth } from "./hooks/use-auth";

Amplify.configure({
  Auth: {
    region: window.REACT_APP_REGION,
    userPoolId: window.REACT_APP_USER_POOL_ID,
    userPoolWebClientId: window.REACT_APP_USER_POOL_CLIENT_ID,
    mandatorySignIn: true,
    oauth:
      window.REACT_APP_EXTERNAL_IDP !== "None"
        ? {
            domain: window.REACT_APP_EXTERNAL_DOMAIN,
            scope: ["email", "openid", "profile"],
            redirectSignIn: window.REACT_APP_EXTERNAL_REDIRECT,
            redirectSignOut: window.REACT_APP_EXTERNAL_REDIRECT,
            responseType: "code",
          }
        : {},
  },
});

const getUserInfo = (userSession) => {
  const payload = userSession.idToken.payload;
  let groups = [];
  if ("custom:teams" in payload) {
    groups = payload["custom:teams"].slice(1, -1).split(", ");
  } else if ("cognito:groups" in payload) {
    groups = payload["cognito:groups"];
  }
  const userInfo = {
    email: payload["email"],
    username: payload["cognito:username"],
    groups: groups,
    jwt: userSession.idToken.jwtToken,
  };
  console.log("userInfo", userInfo);
  return userInfo;
};

const contentRouter = (userSession) => {
  console.log("userSession", userSession);
  if (userSession != null) {
    return <Teams userInfo={getUserInfo(userSession)} />;
  } else if (window.REACT_APP_EXTERNAL_IDP !== "None") {
    return <SignInExternal />;
  } else {
    return <SignIn />;
  }
};

const App = () => <Frame content={contentRouter(useAuth())} />;

export default App;
