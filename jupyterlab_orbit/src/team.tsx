import React, { useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ReactWidget, ICommandPalette } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';
import { teamIcon } from './common/icons';
import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  RUNNING_CLASS,
  SECTION_CLASS
} from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';
import { request } from './common/backend';
import { ListViewWithRefresh, TreeView } from './common/categoryViews';
const NAME = 'Your Team';
const ICON: LabIcon = teamIcon;

interface IItem {
  name: string;
  value: string;
}

interface IUseItemsReturn {
  commonItems: JSX.Element;
  securityItems: any;
  other: any;
  refreshCallback: () => void;
}

const Item = (props: { item: IItem }) => (
  <li className={ITEM_CLASS}>
    <span className={ITEM_DETAIL_CLASS} title={props.item.name}>
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
  const [data, setData] = useState({
    common: [],
    security: {},
    other: {}
  });

  const refreshCallback = async () => {
    setData(await request('team'));
  };

  useEffect(() => {
    const fetchData = async () => {
      setData(await request('team'));
    };
    fetchData();
  }, []);
  const commonItems = <Items data={data.common} />;
  const securityItems = data.security;
  const other = data.other;
  return { commonItems, securityItems, other, refreshCallback };
};

class TeamCentralWidget extends ReactWidget {
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
        <CentralWidgetHeader name={NAME} icon={ICON} />
        <div />
      </div>
    );
  }
}

const TeamComponentFunc = (): JSX.Element => {
  const { commonItems, securityItems, other, refreshCallback } = useItems();
  return (
    <div>
      <ListViewWithRefresh
        name={'Team'}
        items={commonItems}
        refreshCallback={refreshCallback}
      />
      <TreeView name={'Security'} item={securityItems} root_name={'security'} />
      <TreeView name={'Other'} item={other} root_name={'properties'} />
    </div>
  );
};

class TeamLeftWidget extends ReactWidget {
  launchCallback: () => void;
  app: JupyterFrontEnd;
  constructor({
    openCallback,
    app
  }: {
    openCallback: () => void;
    app: JupyterFrontEnd;
  }) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.icon = ICON;
    this.launchCallback = openCallback;
    this.app = app;
  }

  render(): JSX.Element {
    const refreshCallback1 = () => {
      console.log(`[${NAME}] Refresh!`);
    };
    return (
      <div className={SECTION_CLASS}>
        <LeftWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback1}
          openCallback={this.launchCallback}
          app={this.app}
        />
        <TeamComponentFunc />
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
    widgetCreation: () => new TeamCentralWidget()
  });

  registerGeneral({
    app: app,
    palette: palette,
    launcher: launcher,
    menu: menu,
    rank: rank,
    launchCommand: launchCommand,
    leftWidget: new TeamLeftWidget({
      openCallback: () => {
        commands.execute(launchCommand);
      },
      app
    })
  });
};
