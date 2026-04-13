// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, within } from '@testing-library/react';
import { Button } from '../Button';
import { expectNoA11yViolations } from '../../../__tests__/a11y-utils';

afterEach(() => cleanup());

describe('Button contract', () => {
  /* ---- Identity ---- */
  it('has displayName', () => {
    expect(Button.displayName).toBe('Button');
  });

  it('forwards ref to <button>', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Click</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  /* ---- Variants ---- */
  it.each(['primary', 'secondary', 'outline', 'ghost', 'danger'] as const)(
    'renders variant=%s without crash',
    (variant) => {
      const { container } = render(<Button variant={variant}>V</Button>);
      expect(container.querySelector('button')).toBeInTheDocument();
    },
  );

  /* ---- Sizes ---- */
  it.each(['sm', 'md', 'lg'] as const)('renders size=%s without crash', (size) => {
    const { container } = render(<Button size={size}>S</Button>);
    expect(container.querySelector('button')).toBeInTheDocument();
  });

  /* ---- Disabled ---- */
  it('respects disabled prop', () => {
    const { container } = render(<Button disabled>D</Button>);
    expect(container.querySelector('button')).toBeDisabled();
  });

  /* ---- Loading ---- */
  it('disables button when loading', () => {
    const { container } = render(<Button loading>L</Button>);
    expect(container.querySelector('button')).toBeDisabled();
  });

  /* ---- Access control ---- */
  it('access=hidden returns null', () => {
    const { container } = render(<Button access="hidden">H</Button>);
    expect(container.innerHTML).toBe('');
  });

  it('access=disabled renders disabled button', () => {
    const { container } = render(<Button access="disabled">D</Button>);
    expect(container.querySelector('button')).toBeDisabled();
  });

  it('access=full renders enabled button', () => {
    const { container } = render(<Button access="full">F</Button>);
    expect(container.querySelector('button')).not.toBeDisabled();
  });

  /* ---- Custom className ---- */
  it('merges custom className', () => {
    const { container } = render(<Button className="custom-btn">C</Button>);
    expect(container.querySelector('button')).toHaveClass('custom-btn');
  });

  /* ---- Accessibility ---- */
  it('renders accessible button role by default', () => {
    const { container } = render(<Button>A</Button>);
    const btn = within(container).getByRole('button');
    expect(btn).toBeInTheDocument();
  });
});

describe('Button — accessibility', () => {
  it('has no axe-core a11y violations', async () => {
    const { container } = render(<Button>Click me</Button>);
    await expectNoA11yViolations(container);
  });
});
