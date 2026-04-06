import React, { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FilterValueEditor } from './FilterValueEditor';

const meta: Meta<typeof FilterValueEditor> = {
  title: 'Advanced/DataGrid/FilterBuilder/FilterValueEditor',
  component: FilterValueEditor,
  parameters: { layout: 'centered' },
  decorators: [(Story) => <div style={{ width: 360 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof FilterValueEditor>;

export const TextInput: Story = {
  render: () => {
    const [value, setValue] = useState<unknown>('');
    return (
      <FilterValueEditor
        filterType="text"
        operator="contains"
        value={value}
        onChange={(v) => setValue(v)}
      />
    );
  },
};

export const NumberInput: Story = {
  render: () => {
    const [value, setValue] = useState<unknown>(null);
    return (
      <FilterValueEditor
        filterType="number"
        operator="greaterThan"
        value={value}
        onChange={(v) => setValue(v)}
      />
    );
  },
};

export const NumberRange: Story = {
  render: () => {
    const [value, setValue] = useState<unknown>(10);
    const [valueTo, setValueTo] = useState<unknown>(100);
    return (
      <FilterValueEditor
        filterType="number"
        operator="inRange"
        value={value}
        valueTo={valueTo}
        onChange={(v, vt) => { setValue(v); setValueTo(vt); }}
      />
    );
  },
};

export const DateInput: Story = {
  render: () => {
    const [value, setValue] = useState<unknown>('');
    return (
      <FilterValueEditor
        filterType="date"
        operator="equals"
        value={value}
        onChange={(v) => setValue(v)}
      />
    );
  },
};

export const SetInput: Story = {
  render: () => {
    const [value, setValue] = useState<unknown>([]);
    return (
      <FilterValueEditor
        filterType="set"
        operator="in"
        value={value}
        setValues={['HR', 'Finans', 'IT', 'Operasyon', 'Pazarlama']}
        onChange={(v) => setValue(v)}
      />
    );
  },
};

export const BlankOperator: Story = {
  render: () => (
    <FilterValueEditor
      filterType="text"
      operator="blank"
      value=""
      onChange={() => {}}
    />
  ),
};
