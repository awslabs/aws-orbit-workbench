import teamsSvg from '../../style/icons/team.svg';
import catalogSvg from '../../style/icons/catalog.svg';
import computeSvg from '../../style/icons/compute.svg';
import containersSvg from '../../style/icons/container.svg';
import storageSvg from '../../style/icons/storage.svg';
import testsSvg from '../../style/icons/tests.svg';
import orbitSvg from '../../style/icons/orbit.svg';
import fargateSvg from '../../style/icons/fargate.svg';
import ec2Svg from '../../style/icons/ec2.svg';
import jupyterSvg from '../../style/icons/jupyterlogo.svg';
import sparkSvg from '../../style/icons/apachesparklogo.svg';
import { LabIcon } from '@jupyterlab/ui-components';

export const teamIcon = new LabIcon({
  name: 'teamsIcon',
  svgstr: teamsSvg
});

export const containersIcon = new LabIcon({
  name: 'containersIcon',
  svgstr: containersSvg
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

export const fargateIcon = new LabIcon({
  name: 'fargateIcon',
  svgstr: fargateSvg
});

export const ec2Icon = new LabIcon({
  name: 'ec2Icon',
  svgstr: ec2Svg
});

export const jupyterIcon = new LabIcon({
  name: 'jupyterIcon',
  svgstr: jupyterSvg
});

export const sparkIcon = new LabIcon({
  name: 'sparkIcon',
  svgstr: sparkSvg
});
