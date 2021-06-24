import React from 'react';

import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  SECTION_CLASS,
  SHUTDOWN_BUTTON_CLASS
} from '../common/styles';
import {
  IUseItemsReturn,
  IItem,
  openItemCallback,
  deleteItem,
  getStateIcon
} from '../containers';
import { CategoryViews } from '../common/categoryViews';
import { Tooltip } from 'antd';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import { bugIcon, closeIcon, searchIcon } from '@jupyterlab/ui-components';
import { JupyterFrontEnd } from '@jupyterlab/application';

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
  connect: (
    podName: string,
    containerName: string,
    type: string
  ) => Promise<void>;
  logs: (podName: string, containerName: string, type: string) => Promise<void>;
  type: string;
}) => {
  const { title, color, icon } = getStateIcon(props.item.job_state);
  return (
    <Tooltip placement="topLeft" title={title} color={color} key={'Orbit'}>
      <li className={ITEM_CLASS}>
        <span> {icon} </span>
        <span
          className={ITEM_LABEL_CLASS}
          title={props.item.hint}
          onClick={() => props.openItemCallback(props.item.name)}
        >
          {props.item.job_name}
        </span>
        <span className={ITEM_DETAIL_CLASS}>{props.item.time}</span>
        <span className={ITEM_DETAIL_CLASS}>{props.item.node_type}</span>
        <ToolbarButtonComponent
          className={SHUTDOWN_BUTTON_CLASS}
          icon={bugIcon}
          onClick={() =>
            props.connect(
              props.item.name,
              props.item.container_name,
              props.type
            )
          }
          tooltip={'Connect terminal!'}
          enabled={props.item.job_state === 'running'}
        />
        <ToolbarButtonComponent
          className={SHUTDOWN_BUTTON_CLASS}
          icon={searchIcon}
          onClick={() =>
            props.logs(props.item.name, props.item.container_name, props.type)
          }
          tooltip={'Tail logs!'}
          enabled={props.item.job_state === 'running'}
        />
        <ToolbarButtonComponent
          className={SHUTDOWN_BUTTON_CLASS}
          icon={closeIcon}
          onClick={() => props.closeItemCallback(props.item.name)}
          tooltip={'Shut Down!'}
        />
      </li>
    </Tooltip>
  );
};

const Items = (props: {
  data: IItem[];
  closeItemCallback: (name: string) => void;
  connect: (
    podName: string,
    containerName: string,
    type: string
  ) => Promise<void>;
  logs: (podName: string, containerName: string, type: string) => Promise<void>;
  type: string;
}) => (
  <>
    {' '}
    {props.data.map(x => (
      <Item
        item={x}
        openItemCallback={openItemCallback}
        closeItemCallback={props.closeItemCallback}
        connect={props.connect}
        logs={props.logs}
        type={props.type}
      />
    ))}{' '}
  </>
);

export const ContainerCategoryLeftList = (props: {
  title: string;
  type: string;
  useItems: (type: string, app: JupyterFrontEnd) => IUseItemsReturn;
  key: string;
  openCallback: (name: string) => any;
  app: JupyterFrontEnd;
}): JSX.Element => {
  const {
    data,
    closeAllCallback,
    refreshCallback,
    setData,
    connect,
    logs
  } = props.useItems(props.type, props.app);

  const closeItemCallback = async (name: string) => {
    setData(await deleteItem(name, props.type));
  };
  const items = (
    <Items
      data={data}
      closeItemCallback={closeItemCallback}
      connect={connect}
      logs={logs}
      type={props.type}
    />
  );

  return (
    <div className={SECTION_CLASS}>
      <CategoryViews
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        closeAllCallback={closeAllCallback}
        key={props.key}
        openCallback={props.openCallback}
      />
    </div>
  );
};
