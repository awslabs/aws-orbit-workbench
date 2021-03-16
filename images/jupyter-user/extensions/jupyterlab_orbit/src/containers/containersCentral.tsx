import React from 'react';
import * as utils from '../typings/utils';
import { TableWidget } from './table/table';
import ReactJson from 'react-json-view';
import { IUseItemsReturn } from '../containers';

const columns = [
  {
    title: 'Name',
    dataIndex: 'name',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 3
    }
  },
  {
    title: 'Status',
    dataIndex: 'job_state',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 3
    }
  },
  {
    title: 'Tasks',
    dataIndex: 'tasks',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 3
    },
    render: (text: any, record: any) => {
      return `${JSON.stringify(text)}`;
    }
  },
  {
    title: 'Start Time',
    dataIndex: 'time',
    sorter: {
      compare: utils.Sorter.DEFAULT,
      multiple: 3
    }
  },
  {
    title: 'Node Type',
    dataIndex: 'node_type',
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
          name={'job description'}
          collapsed={1}
          displayDataTypes={false}
        />
      </p>
    )
  };
};

export const ContainerCentralPanel = (props: {
  title: string;
  type: string;
  useItems: (type: string) => IUseItemsReturn;
}): JSX.Element => {
  // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
  // @ts-ignore
  const { data, closeAllCallback, refreshCallback, setData } = props.useItems(
    props.type
  );

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
