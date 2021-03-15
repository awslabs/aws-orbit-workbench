import React, { useEffect, useState } from 'react';
import { Dialog, showDialog } from '@jupyterlab/apputils';

import { TreeView } from '../common/categoryViews';
import { request } from '../common/backend';
import { IDictionary } from '../typings/utils';

const NAME = 'K8Containers';

interface IUseItemsReturn {
  your_jobs: any;
  closeAllCallback: (name: string) => void;
  refreshCallback: () => void;
}

const deleteItem = async (name: string, type: string): Promise<any> => {
  const dataToSend = { name: name };
  try {
    const reply: any | undefined = await request('containers', {
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
  const [your_jobs, setData] = useState([]);

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
        your_jobs.map(async x => {
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

  // const closeItemCallback = async (name: string) => {
  //   console.log(`[${NAME}] Close Item ${name}!`);
  //   setData(await deleteItem(name, type));
  // };

  return { your_jobs, closeAllCallback, refreshCallback };
};

export const ContainerCentralPanel = (props: {
  title: string;
  type: string;
}): JSX.Element => {
  // const { your_jobs, closeAllCallback, refreshCallback } = useItems(props.type);
  const { your_jobs } = useItems(props.type);
  return <TreeView name={'Your jobs'} item={your_jobs} root_name={'jobs'} />;
};
