// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Statistic } from '../Statistic';

afterEach(() => { cleanup(); });

describe('Statistic — temel render', () => {
  it('value gosterir', () => {
    render(<Statistic value={1128} />);
    expect(screen.getByText('1,128')).toBeInTheDocument();
  });
  it('title gosterir', () => {
    render(<Statistic title="Users" value={42} />);
    expect(screen.getByText('Users')).toBeInTheDocument();
  });
  it('prefix ve suffix destekler', () => {
    render(<Statistic value={99} prefix="$" suffix="M" />);
    expect(screen.getByText('$')).toBeInTheDocument();
    expect(screen.getByText('M')).toBeInTheDocument();
  });
  it('precision uygular', () => {
    render(<Statistic value={93.1} precision={2} />);
    expect(screen.getByText('93.10')).toBeInTheDocument();
  });
});

describe('Statistic — trend', () => {
  it('trend up ok gosterir', () => {
    const { container } = render(<Statistic value={100} trend="up" trendValue="+12%" />);
    expect(screen.getByText('+12%')).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeInTheDocument();
  });
});

describe('Statistic — loading', () => {
  it('loading durumunda skeleton gosterir', () => {
    const { container } = render(<Statistic loading />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });
});

describe('Statistic — edge cases', () => {
  it('value=0 "0" olarak gosterir (bos string degil)', () => {
    render(<Statistic value={0} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });
  it('negatif value gosterir', () => {
    render(<Statistic value={-42} />);
    expect(screen.getByText('-42')).toBeInTheDocument();
  });
  it('trend yoksa ok gostermez', () => {
    const { container } = render(<Statistic value={100} />);
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });
});

describe('Statistic — a11y', () => {
  it('data-component attribute vardir', () => {
    const { container } = render(<Statistic value={100} />);
    expect(container.querySelector('[data-component="statistic"]')).toBeInTheDocument();
  });
});
