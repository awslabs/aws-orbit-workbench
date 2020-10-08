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

import "./App.css";
import "antd/dist/antd.css";
import Amplify from "aws-amplify";
import { AuthState } from "@aws-amplify/ui-components";
import useAuth from "./use-auth";
import PageSkeleton from "./page-skeleton";
import SignIn from "./signin";
import AuthenticatedContent from "./authenticated-content";

Amplify.configure({
  Auth: {
    region: window.REACT_APP_REGION,
    userPoolId: window.REACT_APP_USER_POOL_ID,
    userPoolWebClientId: window.REACT_APP_USER_POOL_CLIENT_ID,
    mandatorySignIn: true,
  },
});

const getUserInfo = (userState) => {
  console.log(userState);
  return {
    email: userState.signInUserSession.idToken.payload["email"],
    username: userState.signInUserSession.idToken.payload["cognito:username"],
    groups: userState.signInUserSession.idToken.payload["cognito:groups"],
    jwt: userState.signInUserSession.idToken.jwtToken,
  };
};

function App() {
  const [authState, userState] = useAuth();

  if (authState === AuthState.SignedIn && userState) {
    return PageSkeleton(AuthenticatedContent, getUserInfo(userState));
  } else {
    return PageSkeleton(SignIn, {});
  }
}

export default App;
