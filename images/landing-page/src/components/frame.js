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

import DataMakerLogoImage from "../images/datamaker.png";
import "../App.css";
import { Space, Row } from "antd";

const Frame = ({ content }) => (
  <div className="app-container">
    <Space direction="vertical" size="large" align="center">
      <Row />
      <Row>
        <img className="datamaker-logo" src={DataMakerLogoImage} alt="DataMakerLogo" />
      </Row>
      <Row>
        <div className="datamaker-content"> {content} </div>
      </Row>
    </Space>
  </div>
);

export default Frame;
