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

import { useEffect, useState } from "react";
import { Auth, Hub } from "aws-amplify";
import { onAuthUIStateChange } from "@aws-amplify/ui-components";

const getUserSession = async () => {
  try {
    return await Auth.currentSession();
  } catch (err) {
    return console.log("getUserSession error: ", err);
  }
};

export const useAuth = () => {
  const [userSession, setUser] = useState(null);

  useEffect(() => {
    if (window.REACT_APP_EXTERNAL_IDP === "None") {
      return onAuthUIStateChange((nextAuthState, authData) => {
        console.log("nextAuthState", nextAuthState);
        console.log("authData", authData);
        if (authData) {
          setUser(authData.signInUserSession);
        } else {
          setUser(null);
        }
      });
    }

    Hub.listen("auth", async ({ payload: { event, data } }) => {
      console.log("event", event);
      console.log("data", data);
      switch (event) {
        case "signIn":
        case "cognitoHostedUI":
          setUser(await getUserSession());
          break;
        case "signOut":
          setUser(null);
          break;
        case "signIn_failure":
        case "cognitoHostedUI_failure":
          console.log("Sign in failure", data);
          break;
        default:
          break;
      }
    });

    (async () => setUser(await getUserSession()))();
  }, []);

  return userSession;
};
