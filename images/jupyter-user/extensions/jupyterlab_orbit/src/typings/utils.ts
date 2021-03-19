import moment from 'moment';

export interface IDictionary<TValue> {
  [id: string]: TValue;
}
export const TS_FORMAT = 'yyyy-mm-ddThh:mm:ssZ';
/**
 * @param {string} dateA - a date, represented in string format
 * @param {string} dateB - a date, represented in string format
 */
const dateSort = (dateA: any, dateB: any) =>
  moment(dateA, TS_FORMAT).diff(moment(dateB, TS_FORMAT));

/**
 *
 * @param {number|string} a
 * @param {number|string} b
 */
const defaultSort = (a: any, b: any) => {
  if (a < b) {
    return -1;
  }
  if (b < a) {
    return 1;
  }
  return 0;
};

export const Sorter = {
  DEFAULT: defaultSort,
  DATE: dateSort
};
