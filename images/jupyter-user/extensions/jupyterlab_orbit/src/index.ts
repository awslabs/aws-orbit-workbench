import 'antd/dist/antd.css';
import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ICommandPalette } from '@jupyterlab/apputils';
import { ILauncher } from '@jupyterlab/launcher';
import { IMainMenu } from '@jupyterlab/mainmenu';
import { Menu } from '@lumino/widgets';
import { activateCatalog } from './catalog';
import { activateCompute } from './compute';
import { activateStorage } from './storage';
import { activateContainers } from './containers';
import { activateTeam } from './team';
// import { activateTests } from './tests';

const extension: JupyterFrontEndPlugin<void> = {
  id: 'aws-orbit-workbench',
  autoStart: true,
  requires: [ICommandPalette],
  optional: [ILauncher, IMainMenu],
  activate: (
    app: JupyterFrontEnd,
    palette: ICommandPalette,
    launcher: ILauncher | null,
    menu: IMainMenu | null
  ) => {
    console.log('AWS Orbit Workbench extension is activated!!');

    const { commands } = app;
    const orbitMenu: Menu = new Menu({ commands });
    orbitMenu.title.label = 'AWS Orbit Workbench';
    menu.addMenu(orbitMenu, { rank: 80 });

    activateTeam(app, palette, launcher, orbitMenu, 901);
    activateCatalog(app, palette, launcher, orbitMenu, 902);
    activateContainers(app, palette, launcher, orbitMenu, 903);
    activateCompute(app, palette, launcher, orbitMenu, 904);
    activateStorage(app, palette, launcher, orbitMenu, 905);
    // activateTests(app, palette, launcher, orbitMenu, 906);
  }
};

export default extension;
