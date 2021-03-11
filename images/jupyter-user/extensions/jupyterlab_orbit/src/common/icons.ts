import teamsSvg from '../../style/icons/team.svg';
import catalogSvg from '../../style/icons/catalog.svg';
import computeSvg from '../../style/icons/compute.svg';
import storageSvg from '../../style/icons/storage.svg';
import testsSvg from '../../style/icons/tests.svg';
import orbitSvg from '../../style/icons/orbit.svg';
import { LabIcon } from '@jupyterlab/ui-components';

export const teamIcon = new LabIcon({
  name: 'teamsIcon',
  svgstr: teamsSvg
});

export const computeIcon = new LabIcon({
  name: 'computeIcon',
  svgstr: computeSvg
});

export const storageIcon = new LabIcon({
  name: 'storageIcon',
  svgstr: storageSvg
});

export const catalogIcon = new LabIcon({
  name: 'catalogIcon',
  svgstr: catalogSvg
});

export const testsIcon = new LabIcon({
  name: 'testsIcon',
  svgstr: testsSvg
});

export const orbitIcon = new LabIcon({
  name: 'orbitIcon',
  svgstr: orbitSvg
});
