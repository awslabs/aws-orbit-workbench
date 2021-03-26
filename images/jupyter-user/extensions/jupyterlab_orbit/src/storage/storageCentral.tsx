import React from 'react';
import * as utils from '../typings/utils';
import { TableWidget } from '../common/table';
import ReactJson from 'react-json-view';
import { IUseItemsReturn } from '../storage';
import { JupyterFrontEnd } from '@jupyterlab/application';

const columns = [
  {
    title: 'Name',
    dataIndex: 'name',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 2
    }
  },
  {
    title: 'Creation Timestamp',
    dataIndex: 'creationTimestamp',
    sorter: {
      compare: utils.Sorter.DATE,
      multiple: 1
    }
  },
  {
    title: 'Size',
    dataIndex: 'size',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 3
    }
  }
];

const expandable = (): {} => {
  return {
    expandedRowRender: (record: { info: object }) => (
      <p>
        <ReactJson
          src={record.info}
          name={'details'}
          collapsed={1}
          displayDataTypes={false}
        />
      </p>
    )
  };
};

export const StorageCentralPanel = (props: {
  title: string;
  type: string;
  useItems: (type: string, app: JupyterFrontEnd) => IUseItemsReturn;
}): JSX.Element => {
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  const { data, refreshCallback } = props.useItems(props.type);

  return (
    <div>
      <div>
        <TableWidget
          type={props.type}
          title={props.title}
          data={data}
          columns={columns}
          expandable={expandable}
        />
      </div>
    </div>
  );
};
