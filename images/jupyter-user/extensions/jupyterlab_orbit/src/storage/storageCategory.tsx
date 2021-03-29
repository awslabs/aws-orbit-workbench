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
  IItemDeleteResponse
} from '../storage';
import { CategoryViewsNoClose } from '../common/categoryViews';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { deleteItem } from '../storage';
import {
  ToolbarButtonComponent,
  showDialog,
  Dialog
} from '@jupyterlab/apputils';
import { closeIcon } from '@jupyterlab/ui-components';
import { request } from '../common/backend';
import { IDictionary } from '../typings/utils';

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
  const { data, refreshCallback, setData } = props.useItems(
    props.type,
    props.app
  );

  const closeItemCallback = async (name: string) => {
    const response: IItemDeleteResponse = await deleteItem(name, props.type);
    console.log(response);
    if (response.status.toString() === '200') {
      console.log(`Storage ${props.type} ${name} delete succeded`);
      const parameters: IDictionary<number | string> = {
        type: props.type
      };
      console.log(`Fetching latest storage ${props.type} details`);
      setData(await request('storage', parameters));
    } else {
      console.log(`Error deleting storage ${props.type} ${name}`);
      console.log(response);
      void (await showDialog({
        title: 'Storage Error',
        body: response.message,
        buttons: [Dialog.cancelButton({ label: 'Close' })]
      }));
    }
  };

  // const closeItemCallback = async (name: string) => {
  //      setData(await deleteItem(name, props.type));
  // };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;
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
