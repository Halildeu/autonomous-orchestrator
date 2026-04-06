import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FilterCombinatorRow } from './FilterCombinatorRow';
import type { FilterCombinator } from './types';

const meta: Meta<typeof FilterCombinatorRow> = {
  title: 'Advanced/DataGrid/FilterBuilder/FilterCombinatorRow',
  component: FilterCombinatorRow,
  parameters: { layout: 'centered' },
  decorators: [(Story) => <div style={{ width: 400 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof FilterCombinatorRow>;

const andCombinator: FilterCombinator = { type: 'combinator', id: 'c1', logic: 'AND' };
const orCombinator: FilterCombinator = { type: 'combinator', id: 'c2', logic: 'OR' };

export const Default: Story = {
  args: {
    combinator: andCombinator,
    onSetLogic: () => {},
  },
};

export const OrLogic: Story = {
  args: {
    combinator: orCombinator,
    onSetLogic: () => {},
  },
};

export const Disabled: Story = {
  args: {
    combinator: andCombinator,
    onSetLogic: () => {},
    disabled: true,
  },
};
