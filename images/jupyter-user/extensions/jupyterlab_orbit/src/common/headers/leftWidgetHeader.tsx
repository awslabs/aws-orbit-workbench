import React from 'react';
import { LabIcon, refreshIcon, launcherIcon } from '@jupyterlab/ui-components';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import { orbitIcon } from '../icons';

const SECTION_HEADER_CLASS = 'jp-RunningSessions-sectionHeader';

export const LeftWidgetHeader = (props: {
  name: string;
  icon: LabIcon;
  openCallback: () => any;
  refreshCallback: () => any;
}): JSX.Element => (
  <div>
    <div style={{ textAlign: 'center' }}>
      <orbitIcon.react tag="span" height="80px" width="80px" />
    </div>
    <header
      className={SECTION_HEADER_CLASS}
      style={{ borderBottom: '3px solid var(--jp-border-color2)' }}
    >
      <div
        style={{ display: 'flex', flexDirection: 'row', paddingLeft: '5px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <props.icon.react tag="div" height="24px" width="24px" />
        </div>
        <h2 style={{ fontWeight: 'bold' }}> {props.name} </h2>
      </div>
      <ToolbarButtonComponent
        tooltip={'Open'}
        icon={launcherIcon}
        onClick={props.openCallback}
      />
      <ToolbarButtonComponent
        tooltip={'Refresh List'}
        icon={refreshIcon}
        onClick={props.refreshCallback}
      />
    </header>
  </div>
);
