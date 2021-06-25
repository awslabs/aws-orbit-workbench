import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  Dialog,
  ICommandPalette,
  ReactWidget,
  showDialog,
  MainAreaWidget
} from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Menu } from '@lumino/widgets';

import { containersIcon } from './common/icons';
import {
  Ec2Icon,
  FargateIcon,
  JupyterIcon,
  SparkIcon
} from './common/reactIcons';
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
  QuestionOutlined,
  ScheduleOutlined
} from '@ant-design/icons';

import { request } from './common/backend';
import { IDictionary } from './typings/utils';

const NAME = 'Containers';
const ICON: LabIcon = containersIcon;

const refreshCallback = () => {
  console.log(`[${NAME}] Refresh!`);
};

export interface IItem {
  name: string;
  hint: string;
  time: string;
  node_type: string;
  job_state: string;
  job_name: string;
  pod_app: string;
  container_name: string;
}

export interface IUseItemsReturn {
  data: any[];
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
  setData: Dispatch<SetStateAction<any[]>>;
  connect: (
    podName: string,
    containerName: string,
    type: string
  ) => Promise<void>;
  logs: (podName: string, containerName: string, type: string) => Promise<void>;
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
  let title = 'Unknown State: ' + jobState;
  let color = 'gray';
  let icon: JSX.Element = <QuestionOutlined style={{ color: color }} />;
  switch (jobState) {
    case 'failed':
      title = 'Failed!';
      color = 'red';
      icon = <CloseOutlined style={{ color: color }} />;
      break;
    case 'pending':
    case 'submitted':
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
    case 'active':
      title = 'Active!';
      color = 'green';
      icon = <ScheduleOutlined style={{ color: color }} />;
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
      color = 'orange';
      icon = <FargateIcon />;
      break;
    case 'ec2':
      title = 'EC2';
      color = 'yellow';
      icon = <Ec2Icon />;
      break;
    default:
      console.error(`node_type: ${nodeType}`);
  }
  return { title, color, icon };
};

export const getAppType = (
  appType: string
): {
  title: string;
  color: string;
  icon: JSX.Element;
} => {
  let title = 'Unknown State';
  let color = 'gray';
  let icon: JSX.Element = <QuestionOutlined style={{ color: color }} />;
  switch (appType) {
    case 'orbit-runner':
      title = 'Jupyter';
      color = 'blue';
      icon = <JupyterIcon />;
      break;
    case 'emr-spark':
      title = 'Spark';
      color = 'orange';
      icon = <SparkIcon />;
      break;
    default:
      console.error(`app_type: ${appType}`);
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

const useItems = (type: string, app: JupyterFrontEnd): IUseItemsReturn => {
  const [data, setData] = useState([]);

  const updateData = (data: any[]) => {
    let i = 0;
    data.forEach(r => {
      r.key = i;
      i += 1;
    });
  };

  const connect = async (
    podName: string,
    containerName: string,
    type: string
  ): Promise<void> => {
    const session = await app.serviceManager.terminals.startNew();
    const terminal = await app.commands.execute('terminal:create-new', {
      name: session.name
    });
    let command;
    let namespace;
    if (type === 'user') {
      namespace = '$AWS_ORBIT_USER_SPACE';
    } else {
      namespace = '$AWS_ORBIT_TEAM_SPACE';
    }

    if (
      typeof containerName === 'undefined' ||
      containerName === null ||
      containerName.length === 0
    ) {
      command =
        'kubectl -n ' +
        namespace +
        ' exec --stdin --tty ' +
        podName +
        ' -- /bin/bash \n';
    } else {
      command =
        'kubectl -n ' +
        namespace +
        ' exec --stdin --tty ' +
        podName +
        ' --container ' +
        containerName +
        ' -- /bin/bash \n';
    }

    terminal.content.session.send({
      type: 'stdin',
      content: [command]
    });
    console.log('session', terminal.content.session);
    console.log('terminal', terminal);
  };

  const logs = async (
    podName: string,
    containerName: string,
    type: string
  ): Promise<void> => {
    const session = await app.serviceManager.terminals.startNew();
    const terminal = await app.commands.execute('terminal:create-new', {
      name: session.name
    });
    let command;
    let namespace;
    if (type === 'user') {
      namespace = '$AWS_ORBIT_USER_SPACE';
    } else {
      namespace = '$AWS_ORBIT_TEAM_SPACE';
    }
    if (
      typeof containerName === 'undefined' ||
      containerName === null ||
      containerName.length === 0
    ) {
      command =
        'kubectl logs -n ' + namespace + ' --tail=-1 -f ' + podName + ' \n';
    } else {
      command =
        'kubectl logs -n ' +
        namespace +
        ' --tail=-1 -f ' +
        podName +
        ' -c ' +
        containerName +
        ' \n';
    }

    terminal.content.session.send({
      type: 'stdin',
      content: [command]
    });
    console.log('session', terminal.content.session);
    console.log('terminal', terminal);
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

  return { data, closeAllCallback, refreshCallback, setData, connect, logs };
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
      <ContainerCategoryLeftList
        title={'Your Jobs'}
        type={'user'}
        useItems={useItems}
        key="1"
        openCallback={() => launchSectionWidget('Your Jobs', 'user')}
        app={props.app}
      />
      <ContainerCategoryLeftList
        title={'Team Jobs'}
        type={'team'}
        useItems={useItems}
        key="2"
        openCallback={() => launchSectionWidget('Team Jobs', 'team')}
        app={props.app}
      />
      <ContainerCategoryLeftList
        title={'Cron Jobs'}
        type={'cron'}
        useItems={useItems}
        key="3"
        openCallback={() => launchSectionWidget('Cron Jobs', 'cron')}
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
        <CentralWidgetHeader name={this.title.label} icon={ICON} />
        <ContainerCentralPanel
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
        <CentralWidgetHeader name={NAME} icon={ICON} />
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
    console.log('app', this.app);
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
      app: app
    })
  });
};
