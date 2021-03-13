import React, { useState, useEffect } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  ReactWidget,
  ICommandPalette,
  showDialog,
  Dialog,
  ToolbarButtonComponent
} from '@jupyterlab/apputils';
import { LabIcon, closeIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';
import { Tree } from 'antd';

import { catalogIcon, orbitIcon } from './common/icons';
import {
  RUNNING_CLASS,
  SECTION_CLASS,
  ITEM_CLASS,
  ITEM_LABEL_CLASS,
  ITEM_DETAIL_CLASS,
  SHUTDOWN_BUTTON_CLASS
} from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';
import { request } from './common/backend';
import { ListView } from './common/listView';

const NAME = 'Catalog';
const ICON: LabIcon = catalogIcon;

interface IItem {
  name: string;
  description: string;
}

interface IUseItemsReturn {
  items: JSX.Element;
  treeItems: any[];
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
}

const openItemCallback = (name: string) => {
  console.log(`[${NAME}] Open Item ${name}!`);
};

const Item = (props: {
  name: string;
  description: string;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
}) => (
  <li className={ITEM_CLASS}>
    <orbitIcon.react tag="span" stylesheet="runningItem" />
    <span
      className={ITEM_LABEL_CLASS}
      title={'TITLE'}
      onClick={() => props.openItemCallback(props.name)}
    >
      {props.name}
    </span>
    <span className={ITEM_DETAIL_CLASS}>{props.description}</span>
    <ToolbarButtonComponent
      className={SHUTDOWN_BUTTON_CLASS}
      icon={closeIcon}
      onClick={() => props.closeItemCallback(props.name)}
      tooltip={'Shut Down!'}
    />
  </li>
);

const Items = (props: {
  data: IItem[];
  closeItemCallback: (name: string) => void;
}) => (
  <>
    {' '}
    {props.data.map(x => (
      <Item
        name={x.name}
        description={x.description}
        openItemCallback={openItemCallback}
        closeItemCallback={props.closeItemCallback}
      />
    ))}{' '}
  </>
);

const deleteItem = async (name: string): Promise<IItem[]> => {
  const dataToSend = { name: name };
  try {
    const reply: IItem[] | undefined = await request('catalog', {
      body: JSON.stringify(dataToSend),
      method: 'DELETE'
    });
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE /catalog ${dataToSend}.\n${reason}`);
    return [];
  }
};

const useItems = (): IUseItemsReturn => {
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      setData(await request('catalog'));
    };
    fetchData();
  }, []);

  const closeAllCallback = (name: string) => {
    void showDialog({
      title: `General ${name} shut down`,
      body: 'Are you sure about it?',
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Shut Down All' })
      ]
    }).then(result => {
      if (result.button.accept) {
        console.log('SHUTDOWN ALL!');
        data.map(async x => {
          await deleteItem(x.name);
        });
        setData([]);
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    setData(await request('catalog'));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    setData(await deleteItem(name));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  const [treeItems, setTreeItems] = useState([]);
  useEffect(() => {
    const fetchData = async () => {
      setTreeItems(await request('tree'));
    };
    fetchData();
  }, []);

  return { items, treeItems, closeAllCallback, refreshCallback };
};

const onSelect = (selectedKeys: React.Key[], info: any) => {
  console.log('selected', selectedKeys, info);
};

const CentralWidgetComponent = (): JSX.Element => {
  const { items, treeItems, closeAllCallback, refreshCallback } = useItems();
  return (
    <div className={SECTION_CLASS}>
      <CentralWidgetHeader
        name={NAME}
        icon={ICON}
        refreshCallback={refreshCallback}
      />
      <ListView
        name={'Section1'}
        items={items}
        shutdownAllLabel="Shut Down All"
        closeAllCallback={closeAllCallback}
      />
      <ListView
        name={'Section2'}
        items={items}
        shutdownAllLabel="Shut Down All"
        closeAllCallback={closeAllCallback}
      />
      <Tree
        showLine={true}
        showIcon={false}
        defaultExpandedKeys={['0-0-0']}
        onSelect={onSelect}
        treeData={treeItems}
      />
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
        showIcon={false}
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
