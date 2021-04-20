import React, { useEffect, useState } from 'react';
import { closeIcon } from '@jupyterlab/ui-components';
import {
  Dialog,
  showDialog,
  showErrorMessage,
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
import { RedshiftClusterForm } from '../widgets/CreateRedshiftClusterBox';
import { IItemDeleteResponse } from '../storage';

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

export interface IItemCreateResponse {
  status: string;
  message: string;
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

  const createItem = async (
    name: string,
    numberofnodes: string,
    nodetype: string
  ): Promise<IItemDeleteResponse> => {
    const dataToSend = {
      name: name,
      numberofnodes: numberofnodes,
      nodetype: nodetype
    };
    try {
      const parameters: IDictionary<number | string> = {
        type: type
      };
      const reply: IItemDeleteResponse | undefined = await request(
        'redshift',
        parameters,
        {
          body: JSON.stringify(dataToSend),
          method: 'POST'
        }
      );
      return reply;
    } catch (reason) {
      console.error(`Error creating cluster ${dataToSend}.\n${reason}`);
      return { message: '', reason: '', status: '' };
    }
  };

  const createCallback = async () => {
    void showDialog({
      title: 'Create Redshift Cluster',
      body: new RedshiftClusterForm(),
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Create' })
      ]
    }).then(async result => {
      console.log(result.value);
      if (result.button.accept) {
        const response: IItemCreateResponse = await createItem(
          result.value.name,
          result.value.numberofnodes,
          result.value.nodetype
        );
        console.log(response);
        if (response.status.toString() === '200') {
          console.log(response.message);
          setData(await request('redshift'));
          showErrorMessage('Success', response.message, [
            Dialog.warnButton({ label: 'Dismiss' })
          ]);
        } else {
          console.log(response.message);
          showErrorMessage('Error', response.message, [
            Dialog.warnButton({ label: 'Dismiss' })
          ]);
        }
        console.log('CREATE REDSHIFT CLUSTER!');
      }
    });
  };

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    setData(await request('redshift'));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    const closeMessage = `Delete redshift cluster ${name} ?`;
    void showDialog({
      title: 'Delete',
      body: closeMessage,
      buttons: [
        Dialog.cancelButton({ label: 'Cancel' }),
        Dialog.warnButton({ label: 'Proceed' })
      ]
    }).then(async result => {
      console.log(result.value);
      if (result.button.accept) {
        setData(await deleteItem(name));
      }
    });
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  return { items, closeAllCallback, refreshCallback, createCallback };
};

// eslint-disable-next-line @typescript-eslint/ban-ts-ignore
// @ts-ignore
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

// eslint-disable-next-line @typescript-eslint/ban-ts-ignore
// @ts-ignore
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
