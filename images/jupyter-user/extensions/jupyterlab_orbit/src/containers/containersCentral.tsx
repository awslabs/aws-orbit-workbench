import React from 'react';
import * as utils from '../typings/utils';
import { TableWidget } from './table/table';
import ReactJson from 'react-json-view';
import { IUseItemsReturn, getStateIcon, getNodeType } from '../containers';
import { Tooltip } from 'antd';

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
    title: 'Status',
    dataIndex: 'job_state',
    defaultSortOrder: 'descend',
    sorter: {
      compare: (a: string, b: string) => {
        console.log(`Sorting a=${a} b=${b}`);
        if (a === b) {
          return 0;
        }
        if (a === 'running') {
          return 1;
        }
        if (b === 'running') {
          return 2;
        }
        return 0;
      },
      multiple: 1
    },
    render: (text: any, record: any) => {
      const { title, color, icon } = getStateIcon(text);
      return (
        <Tooltip placement="topLeft" title={title} color={color} key={'Orbit'}>
          <span> {icon} </span>
        </Tooltip>
      );
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
      return (
        <Tooltip
          placement="topLeft"
          title={`${JSON.stringify(text)}`}
          key={'Orbit'}
        >
          <span> record.notebook </span>
        </Tooltip>
      );
    }
  },
  {
    title: 'Start Time',
    dataIndex: 'time',
    sorter: {
      compare: utils.Sorter.DATE,
      multiple: 3
    }
  },
  {
    title: 'Completion Time',
    dataIndex: 'completionTime',
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
      multiple: 4
    },
    render: (text: any, record: any) => {
      const { title, color, icon } = getNodeType(text);
      return (
        <Tooltip placement="topLeft" title={title} color={color} key={'Orbit'}>
          <div> {icon} </div>
        </Tooltip>
      );
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
