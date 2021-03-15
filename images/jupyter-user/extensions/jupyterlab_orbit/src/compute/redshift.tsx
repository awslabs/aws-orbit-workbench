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

import { CategoryViews } from '../common/categoryViews';
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
      title={props.item.hint}
      onClick={() => props.openItemCallback(props.item.name)}
    >
      {props.item.name}
    </span>
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

const deleteItem = async (name: string, type: string): Promise<IItem[]> => {
  const dataToSend = { name: name };
  try {
    const reply: IItem[] | undefined = await request('containers', {
      body: JSON.stringify(dataToSend),
      method: 'DELETE'
    });
    return reply;
  } catch (reason) {
    console.error(`Error on DELETE /containers ${dataToSend}.\n${reason}`);
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
          await deleteItem(x.name, type);
        });
        setData([]);
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    // const parameters: IDictionary<number | string> = {
    //   type: type
    // };
    // setData(await request('containers', parameters));
    setData(await request('redshift'));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    // MYTODO - Pass specific parameter to delete the cluster.
    //setData(await deleteItem(name, type));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  return { items, closeAllCallback, refreshCallback };
};

export const RedshiftCategoryLeftList = (props: {
  title: string;
  type: string;
}): JSX.Element => {
  const { items, closeAllCallback, refreshCallback } = useItems(props.type);
  return (
    <div className={SECTION_CLASS}>
      <CategoryViews
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        closeAllCallback={closeAllCallback}
      />
    </div>
  );
};

export const RedshiftCategoryCentralList = (props: {
  title: string;
  type: string;
}): JSX.Element => {
  const { items, closeAllCallback, refreshCallback } = useItems(props.type);
  return (
    <div className={SECTION_CLASS}>
      <CategoryViews
        name={props.title}
        items={items}
        refreshCallback={refreshCallback}
        closeAllCallback={closeAllCallback}
      />
    </div>
  );
};