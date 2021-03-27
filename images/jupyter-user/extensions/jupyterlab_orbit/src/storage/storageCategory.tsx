import React from 'react';

import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  SECTION_CLASS,
  SHUTDOWN_BUTTON_CLASS
} from '../common/styles';
import { IUseItemsReturn, IItem, openItemCallback } from '../storage';
import { CategoryViews, CategoryViewsNoClose } from '../common/categoryViews';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { deleteItem } from '../containers';
import { ToolbarButtonComponent } from '@jupyterlab/apputils';
import { closeIcon } from '@jupyterlab/ui-components';

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
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
      <span className={ITEM_DETAIL_CLASS}>{props.item.creationTimestamp}</span>
      <span className={ITEM_DETAIL_CLASS}>{props.item.size}</span>
      <ToolbarButtonComponent
        className={SHUTDOWN_BUTTON_CLASS}
        icon={closeIcon}
        onClick={() => props.closeItemCallback(props.item.name)}
        tooltip={'Shut Down!'}
      />
    </li>
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

export const StorageCategoryLeftList = (props: {
  title: string;
  type: string;
  useItems: (type: string, app: JupyterFrontEnd) => IUseItemsReturn;
  key: string;
  openCallback: (name: string) => any;
  app: JupyterFrontEnd;
}): JSX.Element => {
  const { data, closeAllCallback, refreshCallback, setData } = props.useItems(
    props.type,
    props.app
  );

  const closeItemCallback = async (name: string) => {
    setData(await deleteItem(name, props.type));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;
  if (props.type === 'clusterstorageclass') {
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
  } else {
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
  }
};
