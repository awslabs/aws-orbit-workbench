import React, { useState, useEffect } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ReactWidget, MainAreaWidget} from '@jupyterlab/apputils';
import { spreadsheetIcon } from '@jupyterlab/ui-components';
import { Table } from 'antd';
import { ColumnsType } from 'antd/lib/table';
import { TableProps } from 'rc-table/lib/Table';

import { request } from './common/backend';
import { RUNNING_CLASS } from './common/styles';

const NAME = 'Table';
const ICON = spreadsheetIcon

export interface ITableData {
  dataSource: TableProps<any>['data']
  columns: ColumnsType<any>
}

const MainComponent = (): JSX.Element => {

  const [tableData, setTableData] = useState<ITableData>({
    dataSource: [],
    columns: []
  });

  useEffect(() => {
    const fetchData = async () => {
      setTableData(await request<ITableData>('table'));
    };
    fetchData();
  }, []);

  console.log(tableData)

  for (let i in tableData.columns){
    console.log(tableData.columns[i].title)
    const title: string = tableData.columns[i].title.toString().toLowerCase()
    tableData.columns[i]['sorter'] = (a, b) => a[title] - b[title]
  }

  return (
    <div>
      <Table dataSource={tableData['dataSource']} columns={tableData['columns']} />
    </div>
  )
}

class CentralWidget extends ReactWidget {
  constructor() {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.label = `Orbit - ${NAME}`;
    this.title.icon = ICON;
  }

  render(): JSX.Element {
    return <MainComponent/>;
  }
}


export const activateTable = (
  app: JupyterFrontEnd,
  launcher: ILauncher | null,
) => {
  const { commands } = app;
  const launchCommand = `aws-orbit-workbench:launch-${NAME}`;

  commands.addCommand(launchCommand, {
    caption: `Launch ${NAME.toLowerCase()}`,
    label: NAME,
    icon: () => (ICON),
    execute: () => {
      const centralWidget = new MainAreaWidget<ReactWidget>({
        content: new CentralWidget()
      });
      centralWidget.title.label = `Orbit - ${NAME}`;
      app.shell.add(centralWidget, 'main');
    }
  });

  if (launcher) {
    launcher.add({ command: launchCommand });
  }

};
