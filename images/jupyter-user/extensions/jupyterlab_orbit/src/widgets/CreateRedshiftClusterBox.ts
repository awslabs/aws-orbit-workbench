import { Dialog } from '@jupyterlab/apputils';
import { Widget } from '@lumino/widgets';

export interface ICluster {
  name: string;
  numberofnodes: string;
  nodetype: string;
}

export class RedshiftClusterForm extends Widget
  implements Dialog.IBodyWidget<ICluster> {
  constructor() {
    super();
    this.node.appendChild(this.createBody());
  }

  private createBody(): HTMLElement {
    const node = document.createElement('div');
    const br1 = document.createElement('br');
    const br2 = document.createElement('br');
    this._name = document.createElement('input');
    this._numberofnodes = document.createElement('input');
    this._nodetype = document.createElement('input');

    this._namelabel = document.createElement('label');
    this._numberofnodeslabel = document.createElement('label');
    this._nodetypelabel = document.createElement('label');

    node.className = 'jp-RedirectForm';
    this._namelabel.innerText = 'Cluster Name';
    this._numberofnodeslabel.innerText = 'Number of nodes';
    this._nodetypelabel.innerText = 'Node Type';
    this._name.defaultValue = 'db-test';
    this._numberofnodes.defaultValue = '3';
    this._nodetype.defaultValue = 'DC2.large';

    node.appendChild(this._namelabel);
    node.appendChild(this._name);
    node.appendChild(br1);
    node.appendChild(this._numberofnodeslabel);
    node.appendChild(this._numberofnodes);
    node.appendChild(br2);
    node.appendChild(this._nodetypelabel);
    node.appendChild(this._nodetype);
    return node;
  }

  getValue(): ICluster {
    const clusterdetails = {
      name: this._name.value,
      numberofnodes: this._numberofnodes.value,
      nodetype: this._nodetype.value
    };
    return clusterdetails;
  }
  private _namelabel: HTMLLabelElement;
  private _numberofnodeslabel: HTMLLabelElement;
  private _nodetypelabel: HTMLLabelElement;
  private _name: HTMLInputElement;
  private _numberofnodes: HTMLInputElement;
  private _nodetype: HTMLInputElement;
}
