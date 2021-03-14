import React, { useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ReactWidget, ICommandPalette } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';

import { orbitIcon, teamIcon } from './common/icons';
import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  RUNNING_CLASS,
  SECTION_CLASS
} from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';
import { request } from './common/backend';
import { ListViewWithoutToolbar } from './common/listViewWithoutToolbar';
const NAME = 'Your Team';
const ICON: LabIcon = teamIcon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
};

interface IItem {
  name: string;
  value: string;
}

interface IUseItemsReturn {
  items: JSX.Element;
}

const Item = (props: { item: IItem }) => (
  <li className={ITEM_CLASS}>
    <orbitIcon.react tag="span" stylesheet="runningItem" />
    <span className={ITEM_LABEL_CLASS} title={props.item.name}>
      {props.item.name}
    </span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.value}</span>
  </li>
);

const Items = (props: { data: IItem[] }) => (
  <>
    {' '}
    {props.data.map(x => (
      <Item item={x} />
    ))}{' '}
  </>
);

const useItems = (): IUseItemsReturn => {
  const [data, setData] = useState([]);
  useEffect(() => {
    const fetchData = async () => {
      setData(await request('team'));
    };
    fetchData();
  }, []);

  const items = <Items data={data} />;
  return { items };
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
    return (
      <div className={SECTION_CLASS}>
        <CentralWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
        />
        <div />
      </div>
    );
  }
}

class LeftWidget extends ReactWidget {
  launchCallback: () => void;

  constructor({ openCallback }: { openCallback: () => void }) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.icon = ICON;
    this.launchCallback = openCallback;
  }

  render(): JSX.Element {
    const { items } = useItems();
    return (
      <div className={SECTION_CLASS}>
        <LeftWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
          openCallback={this.launchCallback}
        />
        <ListViewWithoutToolbar name={'Section2'} items={items} />
      </div>
    );
  }
}

export const activateTeam = (
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
      openCallback: () => {
        commands.execute(launchCommand);
      }
    })
  });
};
