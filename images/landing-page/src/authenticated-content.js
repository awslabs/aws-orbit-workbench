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

import React from "react";
import { Space, List, Tooltip, Typography } from "antd";
import Icon, { LoadingOutlined } from "@ant-design/icons";
import { AmplifySignOut } from "@aws-amplify/ui-react";
import { ReactComponent as JupyterLogo } from "./jupyter.svg";
import useUrls from "./use-urls";

const { Title } = Typography;

const TeamSpaces = (props) => {
  const [urls, isLoading] = useUrls(props.groups, props.jwt);

  const JupyterIcon = (props) => <Icon component={JupyterLogo} {...props} />;
  const username = props.username.charAt(0).toUpperCase() + props.username.slice(1);
  return (
    <div className="teamspaces-container">
      <div className="teamspaces">
        <List
          itemLayout="horizontal"
          bordered
          dataSource={urls}
          header={
            <Title level={5} style={{ textAlign: "center" }}>
              {username}'s teams
            </Title>
          }
          renderItem={(item) => (
            <List.Item
              actions={[
                <Tooltip
                  title={isLoading ? "Loading Jupyter Lab URL..." : "Jupyter Lab"}
                  color={"#2d5cb4"}
                  key={"Jupyter Lab"}
                >
                  <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: "30px" }}>
                    {isLoading ? <LoadingOutlined /> : <JupyterIcon style={{ fontSize: "30px" }} />}
                  </a>
                </Tooltip>,
              ]}
            >
              <List.Item.Meta title={item.title} />
            </List.Item>
          )}
        />
      </div>
    </div>
  );
};

const AuthenticatedContent = (props) => (
  <div className="authenticated-content">
    <Space className="app-container-space" direction="vertical" align="center" size="large">
      <TeamSpaces {...props} />
      <div className="sign-out">
        <AmplifySignOut />
      </div>
    </Space>
  </div>
);

export default AuthenticatedContent;
