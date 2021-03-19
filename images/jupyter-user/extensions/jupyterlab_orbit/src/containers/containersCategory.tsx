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
import { closeIcon } from '@jupyterlab/ui-components';

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
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
          {props.item.name}
        </span>
        <span className={ITEM_DETAIL_CLASS}>{props.item.time}</span>
        <span className={ITEM_DETAIL_CLASS}>{props.item.node_type}</span>
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
}) => (
  <>
    {' '}
    {props.data.map(x => (
      <Item
        item={x}
        openItemCallback={openItemCallback}
        closeItemCallback={props.closeItemCallback}
      />
    ))}{' '}
  </>
);

export const ContainerCategoryLeftList = (props: {
  title: string;
  type: string;
  useItems: (type: string) => IUseItemsReturn;
  key: string;
  openCallback: (name: string) => any;
}): JSX.Element => {
  const { data, closeAllCallback, refreshCallback, setData } = props.useItems(
    props.type
  );

  const closeItemCallback = async (name: string) => {
    setData(await deleteItem(name, props.type));
  };
  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

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
