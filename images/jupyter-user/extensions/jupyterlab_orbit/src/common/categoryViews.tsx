import React from 'react';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import {
  refreshIcon,
  closeIcon,
  addIcon,
  launcherIcon
} from '@jupyterlab/ui-components';
import ReactJson from 'react-json-view';
import { Collapse } from 'antd';

const SECTION_CLASS = 'jp-RunningSessions-section';
const SECTION_HEADER_CLASS = 'jp-RunningSessions-sectionHeader';
const CONTAINER_CLASS = 'jp-RunningSessions-sectionContainer';
const LIST_CLASS = 'jp-RunningSessions-sectionList';

const { Panel } = Collapse;
function callback(key: any) {
  console.log(key);
}

export const CategoryViews = (props: {
  name: string;
  items: JSX.Element;
  refreshCallback: (name: string) => any;
  closeAllCallback: (name: string) => void;
  key: string;
  openCallback: (name: string) => any;
}) => {
  const stopPropagation = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
  };

  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  const genExtra = () => (
    <div>
      <div
        style={{ display: 'flex', alignItems: 'right' }}
        onClick={stopPropagation}
      >
        <ToolbarButtonComponent
          tooltip={'Open'}
          icon={launcherIcon}
          onClick={() => props.openCallback(props.name)}
        />
        <ToolbarButtonComponent
          tooltip={'Refresh List'}
          icon={refreshIcon}
          onClick={() => props.refreshCallback(props.name)}
        />
        <ToolbarButtonComponent
          tooltip={'Close All'}
          icon={closeIcon}
          onClick={() => props.closeAllCallback(props.name)}
        />
      </div>
    </div>
  );

  return (
    <Collapse defaultActiveKey={['1']} onChange={callback}>
      <Panel header={props.name} key={props.key} extra={genExtra()}>
        <div className={CONTAINER_CLASS}>
          <ul className={LIST_CLASS}>{props.items}</ul>
        </div>
      </Panel>
    </Collapse>
  );
};

export const CategoryViewsNoClose = (props: {
  name: string;
  items: JSX.Element;
  refreshCallback: (name: string) => any;
  key: string;
  openCallback: (name: string) => any;
}) => {
  const stopPropagation = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
  };

  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  const genExtra = () => (
    <div>
      <div
        style={{ display: 'flex', alignItems: 'right' }}
        onClick={stopPropagation}
      >
        <ToolbarButtonComponent
          tooltip={'Open'}
          icon={launcherIcon}
          onClick={() => props.openCallback(props.name)}
        />
        <ToolbarButtonComponent
          tooltip={'Refresh List'}
          icon={refreshIcon}
          onClick={() => props.refreshCallback(props.name)}
        />
      </div>
    </div>
  );

  return (
    <Collapse defaultActiveKey={['1']} onChange={callback}>
      <Panel header={props.name} key={props.key} extra={genExtra()}>
        <div className={CONTAINER_CLASS}>
          <ul className={LIST_CLASS}>{props.items}</ul>
        </div>
      </Panel>
    </Collapse>
  );
};

export const CategoryViewsWithCreate = (props: {
  name: string;
  items: JSX.Element;
  refreshCallback: (name: string) => any;
  closeAllCallback: (name: string) => void;
  createCallback: () => any;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <div style={{ display: 'flex', alignItems: 'right' }}>
          <ToolbarButtonComponent
            tooltip={'Create'}
            icon={addIcon}
            onClick={() => props.createCallback()}
          />
          <ToolbarButtonComponent
            tooltip={'Refresh List'}
            icon={refreshIcon}
            onClick={() => props.refreshCallback(props.name)}
          />
          <ToolbarButtonComponent
            tooltip={'Close All'}
            icon={closeIcon}
            onClick={() => props.closeAllCallback(props.name)}
          />
        </div>
      </header>
      <div className={CONTAINER_CLASS}>
        <ul className={LIST_CLASS}> {props.items} </ul>
      </div>
    </div>
  );
};

export const ListViewWithRefresh = (props: {
  name: string;
  refreshCallback: (name: string) => any;
  items: JSX.Element;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <div style={{ display: 'flex', alignItems: 'right' }} />
        <ToolbarButtonComponent
          tooltip={'Refresh List'}
          icon={refreshIcon}
          onClick={() => props.refreshCallback(props.name)}
        />
      </header>
      <div className={CONTAINER_CLASS}>
        <ul className={LIST_CLASS}> {props.items} </ul>
      </div>
    </div>
  );
};

export const TreeView = (props: {
  name: string;
  item: any;
  root_name: string;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <div style={{ display: 'flex', alignItems: 'right' }} />
      </header>
      <div className={CONTAINER_CLASS}>
        <ReactJson
          src={props.item}
          name={props.root_name}
          collapsed={true}
          displayDataTypes={false}
        />
      </div>
    </div>
  );
};

export const TreeViewWithRefresh = (props: {
  name: string;
  item: any;
  root_name: string;
  refreshCallback: () => any;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <div style={{ display: 'flex', alignItems: 'right' }} />
        <ToolbarButtonComponent
          tooltip={'Refresh'}
          icon={refreshIcon}
          onClick={() => props.refreshCallback()}
        />
      </header>
      <div className={CONTAINER_CLASS}>
        <ReactJson
          src={props.item}
          name={props.root_name}
          collapsed={true}
          displayDataTypes={false}
        />
      </div>
    </div>
  );
};
