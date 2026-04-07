// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Result } from '../Result';

afterEach(() => { cleanup(); });

describe('Result — temel render', () => {
  it('baslik gosterir', () => {
    render(<Result status="success" title="Basarili" />);
    expect(screen.getByText('Basarili')).toBeInTheDocument();
  });
  it('alt baslik gosterir', () => {
    render(<Result status="error" title="Hata" subTitle="Detay" />);
    expect(screen.getByText('Detay')).toBeInTheDocument();
  });
  it('extra slot render eder', () => {
    render(<Result status="info" extra={<button>Geri</button>} />);
    expect(screen.getByText('Geri')).toBeInTheDocument();
  });
  it('data-component attribute ekler', () => {
    const { container } = render(<Result status="success" />);
    expect(container.querySelector('[data-component="result"]')).toBeInTheDocument();
  });
});

describe('Result — status varyantlari', () => {
  it.each(['success', 'info', 'warning', 'error', '403', '404', '500'] as const)(
    'status="%s" SVG icon render eder', (status) => {
      const { container } = render(<Result status={status} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    }
  );
  it('custom icon destekler', () => {
    render(<Result status="success" icon={<span data-testid="custom">X</span>} />);
    expect(screen.getByTestId('custom')).toBeInTheDocument();
  });
});

describe('Result — edge cases', () => {
  it('title olmadan status icon gosterir', () => {
    const { container } = render(<Result status="error" />);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });
  it('className forwarding', () => {
    const { container } = render(<Result status="success" className="my-custom" />);
    expect(container.querySelector('.my-custom')).toBeInTheDocument();
  });
});

describe('Result — a11y', () => {
  it('her status icin anlamli ikon gosterir', () => {
    const { container } = render(<Result status="error" title="Hata" />);
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByText('Hata')).toBeInTheDocument();
  });
});
