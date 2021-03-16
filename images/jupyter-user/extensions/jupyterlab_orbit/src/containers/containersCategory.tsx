import React, { useEffect, useState } from 'react';
import { closeIcon } from '@jupyterlab/ui-components';
import {
  Dialog,
  showDialog,
  ToolbarButtonComponent
} from '@jupyterlab/apputils';
import {
  CheckOutlined,
  CloseOutlined,
  QuestionOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import { Tooltip } from 'antd';

import {
  ITEM_CLASS,
  ITEM_DETAIL_CLASS,
  ITEM_LABEL_CLASS,
  SECTION_CLASS,
  SHUTDOWN_BUTTON_CLASS,
  ORBIT_COLOR
} from '../common/styles';
import { CategoryViews } from '../common/categoryViews';
import { request } from '../common/backend';
import { IDictionary } from '../typings/utils';

const NAME = 'K8Containers';

interface IItem {
  name: string;
  hint: string;
  time: string;
  node_type: string;
  job_state: string;
}

interface IUseItemsReturn {
  items: JSX.Element;
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
}

const openItemCallback = (name: string) => {
  console.log(`[${NAME}] Open Item ${name}!`);
};

const getStateIcon = (
  job_state: string
): {
  title: string;
  color: string;
  icon: JSX.Element;
} => {
  let title = 'Unknown State';
  let color = 'gray';
  let icon: JSX.Element = <QuestionOutlined style={{ color: color }} />;
  switch (job_state) {
    case 'failed':
      title = 'Failed!';
      color = 'red';
      icon = <CloseOutlined style={{ color: color }} />;
      break;
    case 'running':
      title = 'Running...';
      color = ORBIT_COLOR;
      icon = <LoadingOutlined style={{ color: color }} />;
      break;
    case 'succeeded':
      title = 'Succeeded!';
      color = 'green';
      icon = <CheckOutlined style={{ color: color }} />;
      break;
    case 'unknown':
      break;
    default:
      console.error(`job_state: ${job_state}`);
  }
  return { title, color, icon };
};

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

const deleteItem = async (name: string, type: string): Promise<IItem[]> => {
  const dataToSend = { name: name };
  try {
    const reply: IItem[] | undefined = await request(
      'containers',
      {},
      {
        body: JSON.stringify(dataToSend),
        method: 'DELETE'
      }
    );
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
      setData(await request('containers', parameters));
    };

    fetchData();
  }, []);

  const closeAllCallback = (name: string) => {
    void showDialog({
      title: `Delete all ${name} jobs`,
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
    const parameters: IDictionary<number | string> = {
      type: type
    };
    setData(await request('containers', parameters));
  };

  const closeItemCallback = async (name: string) => {
    console.log(`[${NAME}] Close Item ${name}!`);
    setData(await deleteItem(name, type));
  };

  const items = <Items data={data} closeItemCallback={closeItemCallback} />;

  return { items, closeAllCallback, refreshCallback };
};

export const ContainerCategoryLeftList = (props: {
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
