import { JupyterFrontEnd } from '@jupyterlab/application';
import {
  ReactWidget,
  MainAreaWidget,
  ICommandPalette
} from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { ILauncher } from '@jupyterlab/launcher';
import { Menu } from '@lumino/widgets';

export const registerLaunchCommand = ({
  name,
  icon,
  app,
  widgetCreation
}: {
  name: string;
  icon: LabIcon;
  app: JupyterFrontEnd;
  widgetCreation: () => ReactWidget;
}): string => {
  const { commands } = app;
  const launchCommand = `aws-orbit-workbench:launch-${name}`;

  commands.addCommand(launchCommand, {
    caption: `Launch ${name.toLowerCase()}`,
    label: name,
    icon: args => (args['isPalette'] ? null : icon),
    execute: () => {
      const centralWidget = new MainAreaWidget<ReactWidget>({
        content: widgetCreation()
      });
      centralWidget.title.label = `Orbit - ${name}`;
      app.shell.add(centralWidget, 'main');
    }
  });

  return launchCommand;
};

export const registerGeneral = ({
  app,
  palette,
  launcher,
  menu,
  rank,
  launchCommand,
  leftWidget
}: {
  app: JupyterFrontEnd;
  palette: ICommandPalette;
  launcher: ILauncher | null;
  menu: Menu;
  rank: number;
  launchCommand: string;
  leftWidget: ReactWidget;
}): void => {
  const widget = new MainAreaWidget<ReactWidget>({ content: leftWidget });
  app.shell.add(widget, 'left', { rank: rank });

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
