import React, {useEffect, useState} from 'react';
import {closeIcon} from '@jupyterlab/ui-components';
import {Dialog, showDialog, ToolbarButtonComponent} from '@jupyterlab/apputils';
import { orbitIcon } from '../common/icons';
import {ITEM_CLASS, ITEM_DETAIL_CLASS, ITEM_LABEL_CLASS, SECTION_CLASS, SHUTDOWN_BUTTON_CLASS} from "../common/styles";

import {ListView} from "../common/listView";
import {request} from "../common/backend";


const NAME = 'K8Containers';

interface IItem {
  name: string;
  start_time: string;
  node_type:string
}

interface IUseItemsReturn {
  items: JSX.Element;
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
}

const openItemCallback = (name: string) => {
  console.log(`[${NAME}] Open Item ${name}!`);
};

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
}) => (
  <li className={ITEM_CLASS}>
    <orbitIcon.react tag="span" stylesheet="runningItem" />
    <span
      className={ITEM_LABEL_CLASS}
      title={'TITLE'}
      onClick={() => props.openItemCallback(props.item.name)}
    >
      {props.item.name}
    </span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.start_time}</span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.node_type}</span>
    <ToolbarButtonComponent
      className={SHUTDOWN_BUTTON_CLASS}
      icon={closeIcon}
      onClick={() => props.closeItemCallback(props.item.name)}
      tooltip={'Shut Down!'}
    />
  </li>
);

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

const deleteItem = async (name: string): Promise<IItem[]> => {
  const dataToSend = { name: name };
  try {
    const reply: IItem[] | undefined = await request('containers', {
      body: JSON.stringify(dataToSend),
      method: 'DELETE'
    });
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE /catalog ${dataToSend}.\n${reason}`);
    return [];
  }
};

const useItems = (): IUseItemsReturn => {
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      setData(await request('containers'));
    };

    fetchData();
  }, []);

  const closeAllCallback = (name: string) => {
    void showDialog({
      title: `General ${name} shut down`,
      body: 'Are you sure about it?',
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Shut Down All' })
      ]
    }).then(result => {
      if (result.button.accept) {
        console.log('SHUTDOWN ALL!');
        data.map(async x => {
          await deleteItem(x.name);
        });
        setData([]);
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    setData(await request('containers'));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    setData(await deleteItem(name));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  return { items, closeAllCallback, refreshCallback };
};

export const K8ContainersLeftList = (props: {
}): JSX.Element => {
  const {items, closeAllCallback} = useItems();
  return (
      <div className={SECTION_CLASS}>
        <ListView
            name={'Your Containers'}
            items={items}
            shutdownAllLabel="Shut Down All"
            closeAllCallback={closeAllCallback}
        />
      </div>
  );
};
