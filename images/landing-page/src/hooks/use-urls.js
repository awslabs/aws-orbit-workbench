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

import { useState, useEffect } from "react";
import AWS from "aws-sdk";
import { Auth } from "aws-amplify";

const toTitleCase = (phrase) => {
  return phrase
    .toLowerCase()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

const fetchParameters = async (groups, idToken, refreshToken) => {
  const session = await Auth.currentSession();
  AWS.config.region = window.REACT_APP_REGION;
  AWS.config.credentials = new AWS.CognitoIdentityCredentials({
    IdentityPoolId: window.REACT_APP_IDENTITY_POOL_ID,
    Logins: {
      [`cognito-idp.${window.REACT_APP_REGION}.amazonaws.com/${window.REACT_APP_USER_POOL_ID}`]: session
        .getIdToken()
        .getJwtToken(),
    },
  });
  let urls = [];
  if (Array.isArray(groups) && groups.length) {
    const envnameprefix = window.REACT_APP_ENV_NAME.concat("-");
    const params = {
      Names: groups.map((x) => `/orbit/${window.REACT_APP_ENV_NAME}/teams/${x.replace(envnameprefix, "")}/context`),
    };
    const ssm = new AWS.SSM();
    // await new Promise(r => setTimeout(r, 3000));
    const response = await ssm.getParameters(params).promise();
    urls = response.Parameters.map((x) => ({
      title: toTitleCase(x.Name.slice(x.Name.slice(0, -8).lastIndexOf("/") + 1, -8).replace("-", " ")),
      url: `http://${JSON.parse(x.Value)["JupyterUrl"]}/hub/login?next=%2Fhub%2Fhome&id_token=${idToken}&refresh_token=${refreshToken}`,
    }));
  }
  console.log("urls", urls);
  return urls;
};

const useUrls = (groups, idToken, refreshToken) => {
  let default_urls = [];
  if (Array.isArray(groups) && groups.length) {
    default_urls = groups.map((x) => ({
      title: toTitleCase(x.replace("-", " ")),
      url: null,
    }));
  }
  const [urls, setUrls] = useState(default_urls);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setUrls(await fetchParameters(groups, idToken, refreshToken));
      setIsLoading(false);
    };

    fetchData();
  }, [groups, idToken, refreshToken]);

  return [urls, isLoading];
};

export default useUrls;
