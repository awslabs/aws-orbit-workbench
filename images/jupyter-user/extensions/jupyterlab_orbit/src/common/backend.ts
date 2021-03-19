import { URLExt } from '@jupyterlab/coreutils';
import { ServerConnection } from '@jupyterlab/services';

import { IDictionary } from '../typings/utils';

const encodeQueryData = (data: IDictionary<any>): string => {
  const ret = [];
  for (const k in data) {
    ret.push(encodeURIComponent(k) + '=' + encodeURIComponent(data[k]));
  }
  return ret.join('&');
};

export async function request<T>(
  endPoint = '',
  parameters: IDictionary<any> = {},
  init: RequestInit = {}
): Promise<T> {
  const settings = ServerConnection.makeSettings();
  let requestUrl = URLExt.join(settings.baseUrl, 'jupyterlab_orbit', endPoint);

  if (Object.entries(parameters).length > 0) {
    requestUrl = requestUrl.concat('?', encodeQueryData(parameters));
  }

  console.log(`Requesting: ${requestUrl}`);
  let response: Response;
  try {
    response = await ServerConnection.makeRequest(requestUrl, init, settings);
  } catch (error) {
    throw new ServerConnection.NetworkError(error);
  }

  let data: any = await response.text();

  if (data.length > 0) {
    try {
      data = JSON.parse(data);
    } catch (error) {
      console.log('Not a JSON response body.', response);
    }
  }

  if (!response.ok) {
    throw new ServerConnection.ResponseError(response, data.message || data);
  }

  return data;
}
