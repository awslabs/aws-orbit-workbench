import React from 'react';
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
import {
  RedshiftCategoryCentralList,
  RedshiftCategoryLeftList
} from './compute/redshift';

const NAME = 'Compute';
const ICON: LabIcon = computeIcon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
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

        <RedshiftCategoryCentralList
          title={'Your Redshift Clusters'}
          type={'user'}
        />
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
        <RedshiftCategoryLeftList
          title={'Your Redshift Clusters'}
          type={'user'}
        />
        <div />
      </div>
    );
  }
}

export const activateCompute = (
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
