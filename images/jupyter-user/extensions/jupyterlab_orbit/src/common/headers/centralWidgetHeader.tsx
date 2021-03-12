import React from 'react';
import { LabIcon, refreshIcon } from '@jupyterlab/ui-components';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import { orbitIcon } from '../icons';

const SECTION_HEADER_CLASS = 'jp-RunningSessions-sectionHeader';

export const CentralWidgetHeader = (props: {
  name: string;
  icon: LabIcon;
  refreshCallback: () => any;
}): JSX.Element => (
  <div>
    <header
      className={SECTION_HEADER_CLASS}
      style={{
        height: '80px',
        paddingRight: '40px',
        paddingLeft: '40px',
        borderBottom: '3px solid var(--jp-border-color2)'
      }}
    >
      <div
        style={{ display: 'flex', flexDirection: 'row', paddingLeft: '5px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <props.icon.react tag="div" height="48px" width="48px" />
        </div>
        <h1> {props.name} </h1>
      </div>
      <div
        style={{ display: 'flex', flexDirection: 'row', paddingLeft: '5px' }}
      >
        <div style={{ textAlign: 'right' }}>
          <orbitIcon.react tag="span" height="80px" width="80px" />
        </div>
        <ToolbarButtonComponent
          tooltip={'Refresh List'}
          icon={refreshIcon}
          onClick={props.refreshCallback}
        />
      </div>
    </header>
  </div>
);
