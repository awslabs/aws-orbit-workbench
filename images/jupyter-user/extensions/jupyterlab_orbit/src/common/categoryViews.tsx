import React from 'react';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import { refreshIcon, closeIcon, addIcon } from '@jupyterlab/ui-components';
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
}) => {
  const handleRefresh = (e: React.FormEvent<HTMLInputElement>) => {
    e.preventDefault();
    e.stopPropagation();
    console.log('stop propagation');
    props.refreshCallback(props.name);
  };

  const genExtra = () => (
    <div>
      <div style={{ display: 'flex', alignItems: 'right' }}>
        <ToolbarButtonComponent
          tooltip={'Refresh List'}
          icon={refreshIcon}
          onClick={() => handleRefresh}
          actualOnClick={true}
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
          <ul className={LIST_CLASS}> {props.items} </ul>
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

export const ListViewWithoutToolbar = (props: {
  name: string;
  items: JSX.Element;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <div style={{ display: 'flex', alignItems: 'right' }} />
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
