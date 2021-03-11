import React from 'react';

const SECTION_CLASS = 'jp-RunningSessions-section';
const SECTION_HEADER_CLASS = 'jp-RunningSessions-sectionHeader';
const SHUTDOWN_ALL_BUTTON_CLASS = 'jp-RunningSessions-shutdownAll';
const CONTAINER_CLASS = 'jp-RunningSessions-sectionContainer';
const LIST_CLASS = 'jp-RunningSessions-sectionList';

export const ListView = (props: {
  name: string;
  items: JSX.Element;
  shutdownAllLabel: string;
  closeAllCallback: (name: string) => void;
}) => {
  return (
    <div className={SECTION_CLASS}>
      <header className={SECTION_HEADER_CLASS}>
        <h2>{props.name}</h2>
        <button
          className={`${SHUTDOWN_ALL_BUTTON_CLASS} jp-mod-styled`}
          onClick={() => props.closeAllCallback(props.name)}
        >
          {props.shutdownAllLabel}
        </button>
      </header>
      <div className={CONTAINER_CLASS}>
        <ul className={LIST_CLASS}> {props.items} </ul>
      </div>
    </div>
  );
};
