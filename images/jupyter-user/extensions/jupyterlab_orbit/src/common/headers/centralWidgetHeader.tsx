import React from 'react';
import { LabIcon } from '@jupyterlab/ui-components';
import { orbitIcon } from '../icons';

const SECTION_HEADER_CLASS = 'jp-RunningSessions-sectionHeader';

export const CentralWidgetHeader = (props: {
  name: string;
  icon: LabIcon;
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
        <h1 style={{ padding: '5px' }}> {props.name} </h1>
      </div>
      <div
        style={{ display: 'flex', flexDirection: 'row', paddingLeft: '5px' }}
      >
        <div style={{ textAlign: 'right' }}>
          <orbitIcon.react tag="span" height="80px" width="80px" />
        </div>
      </div>
    </header>
  </div>
);
