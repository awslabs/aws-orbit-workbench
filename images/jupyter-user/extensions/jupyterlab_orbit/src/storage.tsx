import React, { Dispatch, SetStateAction, useEffect, useState } from 'react';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { ILauncher } from '@jupyterlab/launcher';
import {
  ReactWidget,
  ICommandPalette,
  MainAreaWidget,
  // showDialog,
  // Dialog
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
  creationTimestamp: string;
  size: string;
  provisioner: string;
}

export interface IItemDeleteResponse {
  status: string;
  reason: string;
  message: string;
}

export interface IUseItemsReturn {
  data: any[];
  // closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
  setData: Dispatch<SetStateAction<any[]>>;
}

export const openItemCallback = (name: string) => {
  console.log(`[${NAME} Open Item ${name}!`);
};

export const deleteItem = async (
  name: string,
  type: string
): Promise<IItemDeleteResponse> => {
  const dataToSend = { name: name };
  try {
    const parameters: IDictionary<number | string> = {
      type: type
    };
    const reply: IItemDeleteResponse | undefined = await request(
      'storage',
      parameters,
      {
        body: JSON.stringify(dataToSend),
        method: 'DELETE'
      }
    );
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE ${dataToSend}.\n${reason}`);
    return { message: '', reason: '', status: '' };
  }
};

// export const deleteItem = async (
//   name: string,
//   type: string
// ): Promise<IItem[]> => {
//   const dataToSend = { name: name };
//   try {
//     const parameters: IDictionary<number | string> = {
//       type: type
//     };
//     const reply: IItem[] | undefined = await request(
//       'storage',
//       parameters,
//       {
//         body: JSON.stringify(dataToSend),
//         method: 'DELETE'
//       }
//     );
//     return reply;
//   } catch (reason) {
//     console.error(`Error on DELETE ${dataToSend}.\n${reason}`);
//     return [];
//   }
// };

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

  // const closeAllCallback = (name: string) => {
  //   void showDialog({
  //     title: `Delete all ${name} storage`,
  //     body: 'Are you sure about it?',
  //     buttons: [
  //       Dialog.cancelButton({ label: 'Cancel' }),
  //       Dialog.warnButton({ label: 'Delete All' })
  //     ]
  //   }).then(result => {
  //     if (result.button.accept) {
  //       console.log('DELETE ALL!');
  //       data.map(async x => {
  //         await deleteItem(x.name, type);
  //       });
  //       setData([]);
  //     }
  //   });
  // };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    const parameters: IDictionary<number | string> = {
      type: type
    };
    setData(await request('storage', parameters));
  };

  return { data, refreshCallback, setData };
};

const StorageSections = (props: { app: JupyterFrontEnd }): JSX.Element => {
  const launchSectionWidget = (title: string, type: string) => {
    const centralWidget = new MainAreaWidget<ReactWidget>({
      content: new CentralWidgetSection(title, type)
    });
    props.app.shell.add(centralWidget, 'main');
  };

  return (
    <>
      <StorageCategoryLeftList
        title={'Team PersistentVolumeClaim(PVC)'}
        type={'teampvc'}
        useItems={useItems}
        key="1"
        openCallback={() =>
          launchSectionWidget('Team PersistentVolumeClaim(PVC)', 'teampvc')
        }
        app={props.app}
      />
      <StorageCategoryLeftList
        title={'Cluster PersistentVolume(PV)'}
        type={'clusterpv'}
        useItems={useItems}
        key="2"
        openCallback={() =>
          launchSectionWidget('Cluster PersistentVolume(PV)', 'clusterpv')
        }
        app={props.app}
      />
      <StorageCategoryLeftList
        title={'Cluster StorageClass'}
        type={'clusterstorageclass'}
        useItems={useItems}
        key="3"
        openCallback={() =>
          launchSectionWidget('Cluster StorageClass', 'clusterstorageclass')
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

class StorageCentralWidget extends ReactWidget {
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
        <StorageSections app={this.app} />
        <div />
      </div>
    );
  }
}

class StorageLeftWidget extends ReactWidget {
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
        <StorageSections app={this.app} />
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
    widgetCreation: () => new StorageCentralWidget({ app: app })
  });

  registerGeneral({
    app: app,
    palette: palette,
    launcher: launcher,
    menu: menu,
    rank: rank,
    launchCommand: launchCommand,
    leftWidget: new StorageLeftWidget({
      openCallback: () => {
        commands.execute(launchCommand);
      },
      app
    })
  });
};
