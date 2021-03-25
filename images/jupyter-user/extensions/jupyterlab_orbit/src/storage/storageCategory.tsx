import React from 'react';

import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  SECTION_CLASS
} from '../common/styles';
import { IUseItemsReturn, IItem, openItemCallback } from '../storage';
import { CategoryViewsNoClose } from '../common/categoryViews';
import { JupyterFrontEnd } from '@jupyterlab/application';

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
}) => {
  return (
    <li className={ITEM_CLASS}>
      <span
        className={ITEM_LABEL_CLASS}
        title={props.item.hint}
        onClick={() => props.openItemCallback(props.item.name)}
      >
        {props.item.name}
      </span>
      <span className={ITEM_DETAIL_CLASS}>{props.item.time}</span>
      <span className={ITEM_DETAIL_CLASS}>{props.item.size}</span>
    </li>
  );
};

const Items = (props: { data: IItem[] }) => (
  <>
    {' '}
    {props.data.map(x => (
      <Item item={x} openItemCallback={openItemCallback} />
    ))}{' '}
  </>
);

export const StorageCategoryLeftList = (props: {
  title: string;
  type: string;
  useItems: (type: string, app: JupyterFrontEnd) => IUseItemsReturn;
  key: string;
  openCallback: (name: string) => any;
  app: JupyterFrontEnd;
}): JSX.Element => {
  const { data, refreshCallback } = props.useItems(props.type, props.app);

  const items = <Items data={data} />;

  return (
    <div className={SECTION_CLASS}>
      <CategoryViewsNoClose
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        key={props.key}
        openCallback={props.openCallback}
      />
    </div>
  );
};
