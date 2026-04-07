// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Grid } from '../Grid';

afterEach(() => { cleanup(); });

describe('Grid — temel render', () => {
  it('grid container render eder', () => {
    const { container } = render(<Grid><Grid.Col span={12}>Content</Grid.Col></Grid>);
    expect(container.querySelector('[data-component="grid"]')).toBeInTheDocument();
  });
  it('12 kolon varsayilandir', () => {
    const { container } = render(<Grid><Grid.Col span={6}>A</Grid.Col></Grid>);
    expect(container.querySelector('.grid-cols-12')).toBeInTheDocument();
  });
  it('24 kolon desteklenir', () => {
    const { container } = render(<Grid columns={24}><Grid.Col span={12}>A</Grid.Col></Grid>);
    expect(container.firstElementChild?.className).toContain('grid');
  });
  it('gutter gap class uygular', () => {
    const { container } = render(<Grid gutter={6}><Grid.Col span={12}>A</Grid.Col></Grid>);
    expect(container.querySelector('.gap-6')).toBeInTheDocument();
  });
});

describe('Grid.Col — span ve responsive', () => {
  it('span class uygular', () => {
    render(<Grid><Grid.Col span={8}>Content</Grid.Col></Grid>);
    expect(document.querySelector('.col-span-8')).toBeInTheDocument();
  });
  it('responsive shorthand props destekler', () => {
    render(<Grid><Grid.Col span={12} md={6} lg={4}>Content</Grid.Col></Grid>);
    const col = document.querySelector('[data-component="grid-col"]');
    expect(col?.className).toContain('col-span-12');
    expect(col?.className).toContain('md:col-span-6');
    expect(col?.className).toContain('lg:col-span-4');
  });
  it('offset class uygular', () => {
    render(<Grid><Grid.Col span={4} offset={2}>Content</Grid.Col></Grid>);
    expect(document.querySelector('.col-start-3')).toBeInTheDocument();
  });
});

describe('Grid — edge cases', () => {
  it('bos children render eder', () => {
    const { container } = render(<Grid />);
    expect(container.querySelector('[data-component="grid"]')).toBeInTheDocument();
  });
  it('className forwarding', () => {
    const { container } = render(<Grid className="my-grid"><Grid.Col span={12}>A</Grid.Col></Grid>);
    expect(container.querySelector('.my-grid')).toBeInTheDocument();
  });
  it('nested grid destekler', () => {
    render(
      <Grid>
        <Grid.Col span={6}>
          <Grid><Grid.Col span={12}>Nested</Grid.Col></Grid>
        </Grid.Col>
      </Grid>
    );
    expect(screen.getByText('Nested')).toBeInTheDocument();
  });
});
