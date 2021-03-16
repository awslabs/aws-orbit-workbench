import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  Dialog,
  ICommandPalette,
  ReactWidget,
  showDialog
} from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';

import { containersIcon, fargateIcon, ec2Icon } from './common/icons';
import { ORBIT_COLOR, RUNNING_CLASS, SECTION_CLASS } from './common/styles';
import { CentralWidgetHeader } from './common/headers/centralWidgetHeader';
import { LeftWidgetHeader } from './common/headers/leftWidgetHeader';
import { registerGeneral, registerLaunchCommand } from './common/activation';
import { ContainerCategoryLeftList } from './containers/containersCategory';
import { ContainerCentralPanel } from './containers/containersCentral';
import {
  CheckOutlined,
  CloseOutlined,
  LoadingOutlined,
  QuestionOutlined
} from '@ant-design/icons';

import { request } from './common/backend';
import { IDictionary } from './typings/utils';

const NAME = 'Containers';
const ICON: LabIcon = containersIcon;

const FARGATE_ICON: LabIcon = fargateIcon;
const EC2_ICON: LabIcon = ec2Icon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
};

export interface IItem {
  name: string;
  hint: string;
  time: string;
  node_type: string;
  job_state: string;
}

export interface IUseItemsReturn {
  data: any[];
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
  setData: Dispatch<SetStateAction<any[]>>;
}

export const openItemCallback = (name: string) => {
  console.log(`[${NAME}] Open Item ${name}!`);
};

export const getStateIcon = (
  jobState: string
): {
  title: string;
  color: string;
  icon: JSX.Element;
} => {
  let title = 'Unknown State';
  let color = 'gray';
  let icon: JSX.Element = <QuestionOutlined style={{ color: color }} />;
  switch (jobState) {
    case 'failed':
      title = 'Failed!';
      color = 'red';
      icon = <CloseOutlined style={{ color: color }} />;
      break;
    case 'running':
      title = 'Running...';
      color = ORBIT_COLOR;
      icon = <LoadingOutlined style={{ color: color }} />;
      break;
    case 'succeeded':
      title = 'Succeeded!';
      color = 'green';
      icon = <CheckOutlined style={{ color: color }} />;
      break;
    case 'unknown':
      break;
    default:
      console.error(`job_state: ${jobState}`);
  }
  return { title, color, icon };
};

export const getNodeType = (
  nodeType: string
): {
  title: string;
  color: string;
  icon: JSX.Element;
} => {
  let title = 'Unknown State';
  let color = 'gray';
  let icon: JSX.Element = <QuestionOutlined style={{ color: color }} />;
  switch (nodeType) {
    case 'fargate':
      title = 'Fargate';
      color = 'white';
      icon = <FARGATE_ICON.react />;
      break;
    case 'ec2':
      title = 'EC2';
      color = 'white';
      icon = <EC2_ICON.react />;
      break;
    default:
      console.error(`node_type: ${nodeType}`);
  }
  return { title, color, icon };
};

export const deleteItem = async (
  name: string,
  type: string
): Promise<IItem[]> => {
  const dataToSend = { name: name };
  try {
    const parameters: IDictionary<number | string> = {
      type: type
    };
    const reply: IItem[] | undefined = await request('containers', parameters, {
      body: JSON.stringify(dataToSend),
      method: 'DELETE'
    });
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE /containers ${dataToSend}.\n${reason}`);
    return [];
  }
};

const useItems = (type: string): IUseItemsReturn => {
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
      const data: any[] = await request('containers', parameters);
      updateData(data);

      setData(data);
    };

    fetchData();
  }, []);

  const closeAllCallback = (name: string) => {
    void showDialog({
      title: `Delete all ${name} jobs`,
      body: 'Are you sure about it?',
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Shut Down All' })
      ]
    }).then(result => {
      if (result.button.accept) {
        console.log('SHUTDOWN ALL!');
        data.map(async x => {
          await deleteItem(x.name, type);
        });
        setData([]);
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    const parameters: IDictionary<number | string> = {
      type: type
    };
    setData(await request('containers', parameters));
  };

  return { data, closeAllCallback, refreshCallback, setData };
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
        <ContainerCentralPanel
          title={'Your Jobs'}
          type={'user'}
          useItems={useItems}
        />
        {/*<ContainerCentralPanel title={'Team Jobs'} type={'team'} />*/}
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
    return (
      <div className={SECTION_CLASS}>
        <LeftWidgetHeader
          name={NAME}
          icon={ICON}
          refreshCallback={refreshCallback}
          openCallback={this.launchCallback}
        />
        <ContainerCategoryLeftList
          title={'Your Jobs'}
          type={'user'}
          useItems={useItems}
        />
        <ContainerCategoryLeftList
          title={'Team Jobs'}
          type={'team'}
          useItems={useItems}
        />
        <ContainerCategoryLeftList
          title={'Cron Jobs'}
          type={'cron'}
          useItems={useItems}
        />
        <div />
      </div>
    );
  }
}

export const activateContainers = (
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
