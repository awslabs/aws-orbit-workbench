import React, { useEffect } from 'react';
import * as utils from '../typings/utils';
import { TableWidget } from '../common/table';
import ReactJson from 'react-json-view';
import { IUseItemsReturn } from '../storage';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { IDictionary } from '../typings/utils';

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

  const getColumns = () => {
    let columns: IDictionary<any> = [];
    console.log(`Storage type=${props.type}`);
    if (props.type === 'teampvc' || props.type === 'clusterpv') {
      columns = [
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
    } else if (props.type === 'clusterstorageclass') {
      columns = [
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
          title: 'Provisioner',
          dataIndex: 'provisioner',
          sorter: {
            compare: utils.Sorter.DEFAULT,
            multiple: 3
          }
        }
      ];
    }

    return columns;
  };

  useEffect(() => {
    const interval = setInterval(refreshCallback, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div>
        <TableWidget
          type={props.type}
          title={props.title}
          data={data}
          columns={getColumns()}
          expandable={expandable}
        />
      </div>
    </div>
  );
};
