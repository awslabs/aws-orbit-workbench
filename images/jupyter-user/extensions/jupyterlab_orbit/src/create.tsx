import React, { useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ReactWidget, ICommandPalette } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';

import { computeIcon } from './common/icons';
import { RUNNING_CLASS, SECTION_CLASS } from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerLaunchCommand, registerGeneral } from './common/activation';

const NAME = 'CreateRedshiftCluster';
const ICON: LabIcon = computeIcon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
};

const CounterComponent = (): JSX.Element => {
  const [counter, setCounter] = useState(0);

  return (
    <div>
      <p>You clicked {counter} times!</p>
      <button
        onClick={(): void => {
          setCounter(counter + 1);
        }}
      >
        Increment
      </button>
    </div>
  );
};

export class CentralWidget extends ReactWidget {
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

        <CounterComponent />
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
    return (
      <div className={SECTION_CLASS}>
        <LeftWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
          openCallback={this.launchCallback}
        />
        <CounterComponent />
      </div>
    );
  }
}

export const activateCreate = (
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
