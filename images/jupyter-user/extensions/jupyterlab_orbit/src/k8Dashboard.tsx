import React, { useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import { ICommandPalette, ReactWidget } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';
import { Input, Space } from 'antd';
import { testsIcon } from './common/icons';
import { RUNNING_CLASS, SECTION_CLASS } from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { registerLaunchCommand } from './common/activation';
const NAME = 'K8Dashboard';
const ICON: LabIcon = testsIcon;
const refreshCallback = (): void => {
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  console.log(`[${NAME}] Refresh!`);
};
const { Search } = Input;

interface IDashboardReturn {
  data: any;
  setData: any;
  onSearch: (value: string) => void;
}

const useItems = (): IDashboardReturn => {
  const [data, setData] = useState({
    url: '',
    hidden: true
  });
  const onSearch = (value: string): void => {
    console.log(`[${value}] Search!`);
    setData({ url: value, hidden: false });
  };

  return { data, setData, onSearch };
};

const DashboardComponentFunc = (): JSX.Element => {
  const { data, onSearch } = useItems();
  return (
    <Space direction="vertical">
      <Search
        placeholder="input search text"
        onSearch={onSearch}
        hidden={!data.hidden}
      />
      <div></div>
      <iframe
        src={data.url}
        sandbox={
          'allow-forms allow-modals allow-orientation-lock allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-presentation allow-same-origin allow-scripts allow-top-navigation allow-top-navigation-by-user-activation'
        }
        hidden={data.hidden}
        id={'dashboard_frame'}
        style={{
          display: 'flex',
          position: 'absolute',
          top: '20px',
          width: '80%',
          height: '80vh'
        }}
        datatype={'text/html'}
      />
    </Space>
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
    return (
      <div className={SECTION_CLASS}>
        <CentralWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
        />
        <div>
          <DashboardComponentFunc />
        </div>
      </div>
    );
  }
}

export const registerDashboard = ({
  app,
  palette,
  launcher,
  menu,
  rank,
  launchCommand
}: {
  app: JupyterFrontEnd;
  palette: ICommandPalette;
  launcher: ILauncher | null;
  menu: Menu;
  rank: number;
  launchCommand: string;
}): void => {
  // Palette
  const category = 'AWS Orbit Workbench';
  palette.addItem({
    command: launchCommand,
    category,
    args: { origin: 'from palette' }
  });

  // Launcher
  if (launcher) {
    launcher.add({ command: launchCommand });
  }
  // Menu
  menu.addItem({ command: launchCommand, args: { origin: 'from the menu' } });
};

export const activateK8Dashboard = (
  app: JupyterFrontEnd,
  palette: ICommandPalette,
  launcher: ILauncher | null,
  menu: Menu,
  rank: number
) => {
  const launchCommand: string = registerLaunchCommand({
    name: NAME,
    icon: ICON,
    app: app,
    widgetCreation: () => new CentralWidget()
  });

  registerDashboard({
    app: app,
    palette: palette,
    launcher: launcher,
    menu: menu,
    rank: rank,
    launchCommand: launchCommand
  });
};
