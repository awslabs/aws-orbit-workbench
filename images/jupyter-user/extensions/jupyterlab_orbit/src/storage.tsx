import React, { useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  ReactWidget,
  ICommandPalette,
  MainAreaWidget
} from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';

import { storageIcon } from './common/icons';
import { RUNNING_CLASS, SECTION_CLASS } from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';
import { request } from './common/backend';
import { IDictionary } from './typings/utils';
import { StorageCentralPanel } from './storage/storageCentral';
import { StorageCategoryLeftList } from './storage/storageCategory';

const NAME = 'Storage';
const ICON: LabIcon = storageIcon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
};

export interface IItem {
  name: string;
  hint: string;
  time: string;
  size: string;
}

export interface IUseItemsReturn {
  data: any[];
  refreshCallback: () => void;
}

export const openItemCallback = (name: string) => {
  console.log(`[${NAME} Open Item ${name}!`);
};

const useItems = (type: string, app: JupyterFrontEnd): IUseItemsReturn => {
  const [data, setData] = useState([]);

  const updateData = (data: any[]) => {
    let i = 0;
    data.forEach(r => {
      r.key = i;
      i += 1;
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      const parameters: IDictionary<number | string> = {
        type: type
      };
      const data: any[] = await request('storage', parameters);
      updateData(data);

      setData(data);
    };

    fetchData();
  }, []);

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    const parameters: IDictionary<number | string> = {
      type: type
    };
    setData(await request('storage', parameters));
  };

  return { data, refreshCallback };
};

const Sections = (props: { app: JupyterFrontEnd }): JSX.Element => {
  const launchSectionWidget = (title: string, type: string) => {
    const centralWidget = new MainAreaWidget<ReactWidget>({
      content: new CentralWidgetSection(title, type)
    });
    props.app.shell.add(centralWidget, 'main');
  };

  return (
    <>
      <StorageCategoryLeftList
        title={'Your Jobs'}
        type={'user'}
        useItems={useItems}
        key="1"
        openCallback={() => launchSectionWidget('Team PVC', 'team')}
        app={props.app}
      />
      <StorageCategoryLeftList
        title={'Team Jobs'}
        type={'team'}
        useItems={useItems}
        key="2"
        openCallback={() => launchSectionWidget('Cluster PV', 'pv')}
        app={props.app}
      />
      <StorageCategoryLeftList
        title={'Cron Jobs'}
        type={'cron'}
        useItems={useItems}
        key="3"
        openCallback={() =>
          launchSectionWidget('Cluster Storage Class', 'storageclass')
        }
        app={props.app}
      />
    </>
  );
};

class CentralWidgetSection extends ReactWidget {
  headerTitle: string;
  type: string;

  constructor(title: string, type: string) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME} - ${title}`;
    this.title.label = `${NAME} - ${title}`;
    this.title.icon = ICON;
    this.headerTitle = title;
    this.type = type;
    console.log(title);
  }

  render(): JSX.Element {
    return (
      <div className={SECTION_CLASS}>
        <CentralWidgetHeader
          name={this.title.label}
          icon={ICON}
          refreshCallback={refreshCallback}
        />
        <StorageCentralPanel
          title={this.headerTitle}
          type={this.type}
          useItems={useItems}
        />
        <div />
      </div>
    );
  }
}

class CentralWidget extends ReactWidget {
  app: JupyterFrontEnd;

  constructor({ app }: { app: JupyterFrontEnd }) {
    super();
    this.addClass('jp-ReactWidget');
    this.addClass(RUNNING_CLASS);
    this.title.caption = `AWS Orbit Workbench - ${NAME}`;
    this.title.label = `Orbit - ${NAME}`;
    this.title.icon = ICON;
    this.app = app;
  }

  render(): JSX.Element {
    return (
      <div className={SECTION_CLASS}>
        <CentralWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
        />
        <Sections app={this.app} />
        <div />
      </div>
    );
  }
}

class LeftWidget extends ReactWidget {
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
    return (
      <div className={SECTION_CLASS}>
        <LeftWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
          openCallback={this.launchCallback}
          app={this.app}
        />
        <Sections app={this.app} />
        <div />
      </div>
    );
  }
}

export const activateStorage = (
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
    widgetCreation: () => new CentralWidget({ app: app })
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
      },
      app
    })
  });
};
