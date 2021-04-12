import React, { useEffect, useState } from 'react';

import { TreeViewWithRefresh } from '../common/categoryViews';
import { request } from '../common/backend';

const NAME = 'Eks';

interface IUseItemsReturn {
  nodeGroups: any;
  refreshCallback: () => void;
}

const useItems = (): IUseItemsReturn => {
  const [data, setData] = useState({
    nodegroups: {}
  });

  useEffect(() => {
    const fetchData = async () => {
      setData(await request('eks'));
    };

    fetchData();
  }, []);

  const refreshCallback = async () => {
    console.log(`[${NAME}] Refresh!`);
    setData(await request('eks'));
  };

  const nodeGroups = data.nodegroups;
  return { nodeGroups, refreshCallback };
};

export const EksComponentFunc = (): JSX.Element => {
  const { nodeGroups, refreshCallback } = useItems();
  return (
    <div>
      <TreeViewWithRefresh
        name={'NodeGroups'}
        item={nodeGroups}
        root_name={'node groups'}
        refreshCallback={refreshCallback}
      />
    </div>
  );
};