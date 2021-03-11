import React from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';

const RUNNING_CLASS = 'jp-RunningSessions';
const SECTION_CLASS = 'jp-RunningSessions-section';

export class Widget extends ReactWidget {
  icon: LabIcon;
  header: JSX.Element;
  content: JSX.Element;

  constructor({
    name,
    icon,
    header,
    content
  }: {
    name: string;
    icon: LabIcon;
    header: JSX.Element;
    content: JSX.Element;
  }) {
    super();
    this.addClass('jp-ReactWidget');
    this.id = name;
    this.title.caption = `AWS Orbit Workbench - ${name}`;
    this.title.icon = icon;
    this.addClass(RUNNING_CLASS);
    this.icon = icon;
    this.header = header;
    this.content = content;
  }

  render(): JSX.Element {
    return (
      <div className={SECTION_CLASS}>
        {' '}
        {this.header} {this.content}
      </div>
    );
  }
}
