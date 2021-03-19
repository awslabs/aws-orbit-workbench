import React, { useEffect, useState } from 'react';
import { closeIcon } from '@jupyterlab/ui-components';
import {
  Dialog,
  showDialog,
  ToolbarButtonComponent
} from '@jupyterlab/apputils';
import { orbitIcon } from '../common/icons';
import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  SECTION_CLASS,
  SHUTDOWN_BUTTON_CLASS
} from '../common/styles';

import { CategoryViewsWithCreate } from '../common/categoryViews';
import { request } from '../common/backend';
import { IDictionary } from '../typings/utils';

const NAME = 'Redshift';

interface IItem {
  name: string;
  hint: string;
  state: string;
  start_time: string;
  node_type: string;
  nodes: string;
}

interface IUseItemsReturn {
  items: JSX.Element;
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
  createCallback: () => void;
}

const openItemCallback = (name: string) => {
  console.log(`[${NAME}] Open Item ${name}!`);
};

const Item = (props: {
  item: IItem;
  openItemCallback: (name: string) => void;
  closeItemCallback: (name: string) => void;
}) => (
  <li className={ITEM_CLASS} draggable={true}>
    <orbitIcon.react tag="span" stylesheet="runningItem" />
    <span
      className={ITEM_LABEL_CLASS}
      title={props.item.hint}
      onClick={() => props.openItemCallback(props.item.name)}
    >
      {props.item.name}
    </span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.state}</span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.start_time}</span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.node_type}</span>
    <span className={ITEM_DETAIL_CLASS}>{props.item.nodes}</span>
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
  console.log('Deleting Redshift Cluster');
  console.log(`DeleteItem ${JSON.stringify(dataToSend)}`);
  try {
    const reply: IItem[] | undefined = await request(
      'redshift',
      {},
      { body: JSON.stringify(dataToSend), method: 'DELETE' }
    );
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE /redshift ${dataToSend}.\n${reason}`);
    return [];
  }
};

const useItems = (type: string): IUseItemsReturn => {
  const [data, setData] = useState([]);
  useEffect(() => {
    const fetchData = async () => {
      const parameters: IDictionary<number | string> = {
        type: type
      };
      console.log(`Parameter ${parameters}`);
      // setData(await request('redshift', parameters));
      setData(await request('redshift'));
    };

    fetchData();
  }, []);

  const closeAllCallback = (name: string) => {
    void showDialog({
      title: `Delete all ${name} redshift clusters`,
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

  const createCallback = () => {
    void showDialog({
      title: 'Create Redshift Cluster',
      body: 'Create Redshift Cluster',
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Create' })
      ]
    }).then(result => {
      if (result.button.accept) {
        console.log('CREATE REDSHIFT CLUSTER!');
        setData([]);
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    setData(await request('redshift'));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    setData(await deleteItem(name));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  return { items, closeAllCallback, refreshCallback, createCallback };
};

export const RedshiftCategoryLeftList = (props: {
  title: string;
  type: string;
}): JSX.Element => {
  const { items, closeAllCallback, refreshCallback, createCallback } = useItems(
    props.type
  );
  return (
    <div className={SECTION_CLASS}>
      <CategoryViewsWithCreate
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        closeAllCallback={closeAllCallback}
        createCallback={createCallback}
      />
    </div>
  );
};

export const RedshiftCategoryCentralList = (props: {
  title: string;
  type: string;
}): JSX.Element => {
  const { items, closeAllCallback, refreshCallback, createCallback } = useItems(
    props.type
  );
  return (
    <div className={SECTION_CLASS}>
      <CategoryViewsWithCreate
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        closeAllCallback={closeAllCallback}
        createCallback={createCallback}
      />
    </div>
  );
};
