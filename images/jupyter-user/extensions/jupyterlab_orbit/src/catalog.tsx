import React, { useState, useEffect } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  ReactWidget,
  ICommandPalette,
  MainAreaWidget
} from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';
import { Tree } from 'antd';
import { IDictionary } from './typings/utils';
import { catalogIcon } from './common/icons';
import { RUNNING_CLASS, SECTION_CLASS } from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';
import { request } from './common/backend';
import { TableOutlined } from '@ant-design/icons';
import DynamicDataTable from '@langleyfoxall/react-dynamic-data-table';

const NAME = 'Catalog';
const ICON: LabIcon = catalogIcon;

interface IUseItemsReturn {
  treeItems: any[];
  refreshCallback: () => void;
}

const useItems = (): IUseItemsReturn => {
  const [treeItems, setTreeItems] = useState([]);
  const updateList = (data: any[]) => {
    data.forEach(database => {
      database.children.forEach((table: { icon: JSX.Element }) => {
        table.icon = <TableOutlined />;
      });
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    const ret: any[] = await request('catalog');
    updateList(ret);
    setTreeItems(ret);
  };

  useEffect(() => {
    const fetchData = async () => {
      const ret: any[] = await request('catalog');
      updateList(ret);
      setTreeItems(ret);
    };
    fetchData();
  }, []);

  return { treeItems, refreshCallback };
};

const CentralWidgetComponent = (props: {
  database: string;
  table: string;
}): JSX.Element => {
  const [state, setState] = useState({
    orderByField: '',
    orderByDirection: 'asc',
    items: []
  });

  useEffect(() => {
    const fetchData = async () => {
      const parameters: IDictionary<number | string> = {
        database: props.database,
        table: props.table,
        field: state.orderByField,
        direction: state.orderByField
      };
      const sorted: any[] = await request('athena', parameters);
      setState({
        orderByField: state.orderByField,
        orderByDirection: state.orderByField,
        items: sorted
      });
    };

    fetchData();
  }, []);

  const changeOrder = async (field: string, direction: string) => {
    console.log(`SORT: [${field}] [${direction}]`);
    const parameters: IDictionary<number | string> = {
      database: props.database,
      table: props.table,
      field: field,
      direction: direction
    };
    const sorted: any[] = await request('athena', parameters);
    setState({
      orderByField: field,
      orderByDirection: direction,
      items: sorted
    });
  };

  return (
    <div className={SECTION_CLASS}>
      <CentralWidgetHeader name={`TABLE ${props.table}`} icon={ICON} />
      {/*  https://github.com/langleyfoxall/react-dynamic-data-table  */}
      <div style={{ display: 'flex' }}>
        <DynamicDataTable
          className="table table-sm table-bordered"
          rows={state.items}
          orderByField={state.orderByField}
          orderByDirection={state.orderByDirection}
          changeOrder={(field: string, direction: string) =>
            changeOrder(field, direction)
          }
          buttons={[]}
        />
      </div>
    </div>
  );
};

class CentralWidget extends ReactWidget {
  database: string;
  table: string;
  constructor(database: string, table: string) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${table}`;
    this.title.label = `Orbit - ${database}.${table}`;
    this.title.icon = ICON;
    this.database = database;
    this.table = table;
  }

  render(): JSX.Element {
    return (
      <CentralWidgetComponent database={this.database} table={this.table} />
    );
  }
}

const LeftWidgetComponent = (props: {
  launchCallback: () => void;
  app: JupyterFrontEnd;
}): JSX.Element => {
  const { treeItems, refreshCallback } = useItems();
  const [state, setState] = useState<any>([
    { database: undefined, table: undefined }
  ]);

  const onSelect = (selectedKeys: React.Key[], info: any) => {
    setState({ database: info.node.db, table: info.node.table });
    console.log('selected', state.database, state.table);
  };

  const launchSectionWidget = () => {
    const centralWidget = new MainAreaWidget<ReactWidget>({
      content: new CentralWidget(state.database, state.table)
    });
    props.app.shell.add(centralWidget, 'main');
  };
  return (
    <div className={SECTION_CLASS}>
      <LeftWidgetHeader
        name={NAME}
        icon={ICON}
        refreshCallback={refreshCallback}
        openCallback={() => launchSectionWidget()}
        app={props.app}
      />
      <Tree
        showLine={true}
        showIcon={true}
        defaultExpandedKeys={['0-0-0']}
        onSelect={onSelect}
        treeData={treeItems}
      />
    </div>
  );
};

class LeftWidget extends ReactWidget {
  launchCallback: () => void;
  app: JupyterFrontEnd;
  constructor({
    launchCallback,
    app
  }: {
    launchCallback: () => void;
    app: JupyterFrontEnd;
  }) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.icon = ICON;
    this.launchCallback = launchCallback;
    this.app = app;
  }

  render(): JSX.Element {
    return (
      <LeftWidgetComponent
        launchCallback={this.launchCallback}
        app={this.app}
      />
    );
  }
}

export const activateCatalog = (
  app: JupyterFrontEnd,
  palette: ICommandPalette,
  launcher: ILauncher | null,
  menu: Menu,
  rank: number
) => {
  const { commands } = app;

  const launchCommand: string = registerLaunchCommand({
    name: NAME,
    icon: ICON,
    app: app,
    widgetCreation: () => new CentralWidget('', NAME)
  });

  registerGeneral({
    app: app,
    palette: palette,
    launcher: launcher,
    menu: menu,
    rank: rank,
    launchCommand: launchCommand,
    leftWidget: new LeftWidget({
      launchCallback: () => {
        commands.execute(launchCommand);
      },
      app: app
    })
  });
};
