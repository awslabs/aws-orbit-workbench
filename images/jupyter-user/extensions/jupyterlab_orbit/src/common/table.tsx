import React from 'react';
import 'antd/dist/antd.css';
import { Table } from 'antd';
import { IDictionary } from '../typings/utils';

export const TableWidget = (props: {
  title: string;
  type: string;
  // closeAllCallback: (name: string) => void;
  // refreshCallback: () => void;
  columns: IDictionary<any>;
  data: any[];
  expandable: () => {};
}): JSX.Element => {
  const tableColumns = props.columns.map(
    (column: { [x: string]: any; sorter: any; dataIndex: any }) => {
      const { sorter, dataIndex, ...otherColumnProps } = column;
      if (sorter) {
        const { compare, ...otherSorterProps } = sorter;

        return {
          ...otherColumnProps,
          dataIndex,
          ellipsis: false,
          sorter: {
            compare: (rowA: any, rowB: any) =>
              compare(rowA[dataIndex], rowB[dataIndex]),
            ...otherSorterProps
          }
        };
      } else {
        return {
          ...column,
          ellipsis: false
        };
      }
    }
  );

  // console.log('******************************');
  // console.log(typeof props.data);
  // console.log(props.data);
  // console.log('******************************');
  // let i = 0;
  // const columnsTest = Object.keys(props.data[0]).map(colName => ({
  //   title: colName,
  //   dataIndex: colName,
  //   sorter: {
  //     compare: colName.includes('time')
  //       ? utils.Sorter.DATE
  //       : utils.Sorter.DEFAULT,
  //     multiple: ++i
  //   }
  // }));
  // console.log(columnsTest);
  // console.log('******************************');

  return (
    <Table
      bordered={false}
      loading={false}
      expandable={props.expandable()}
      title={() => props.title}
      showHeader={true}
      pagination={{ position: ['topLeft', 'bottomRight'] }}
      columns={tableColumns}
      dataSource={props.data}
    />
  );
};
