import React, { useState, useEffect } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ReactWidget, ICommandPalette } from '@jupyterlab/apputils';
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
    const ret: any[] = await request('tree');
    updateList(ret);
    setTreeItems(ret);
  };

  useEffect(() => {
    const fetchData = async () => {
      const ret: any[] = await request('tree');
      updateList(ret);
      setTreeItems(ret);
    };
    fetchData();
  }, []);

  return { treeItems, refreshCallback };
};

const CentralWidgetComponent = (): JSX.Element => {
  const database = 'cms_raw_db';
  const table = 'beneficiary_summary';

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
  };

  const [state, setState] = useState({
    orderByField: '',
    orderByDirection: 'asc',
    items: []
  });
  //

  useEffect(() => {
    const fetchData = async () => {
      const parameters: IDictionary<number | string> = {
        database: database,
        table: table,
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
      database: database,
      table: table,
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
      <CentralWidgetHeader
        name={NAME}
        icon={ICON}
        refreshCallback={refreshCallback}
      />
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
  constructor() {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.label = `Orbit - ${NAME}`;
    this.title.icon = ICON;
  }

  render(): JSX.Element {
    return <CentralWidgetComponent />;
  }
}

const LeftWidgetComponent = (props: {
  launchCallback: () => void;
}): JSX.Element => {
  const { treeItems, refreshCallback } = useItems();
  const [state, setState] = useState<boolean | React.Key[] | any>([
    { selectedKeys: undefined, info: undefined }
  ]);

  const onSelect = (selectedKeys: React.Key[], info: any) => {
    setState({ selectedKeys: selectedKeys, info: info });
    console.log('selected', state.selectedKeys, state.info);
  };

  return (
    <div className={SECTION_CLASS}>
      <LeftWidgetHeader
        name={NAME}
        icon={ICON}
        refreshCallback={refreshCallback}
        openCallback={props.launchCallback}
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

  constructor({ launchCallback }: { launchCallback: () => void }) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.icon = ICON;
    this.launchCallback = launchCallback;
  }

  render(): JSX.Element {
    return <LeftWidgetComponent launchCallback={this.launchCallback} />;
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
    widgetCreation: () => new CentralWidget()
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
      }
    })
  });
};
