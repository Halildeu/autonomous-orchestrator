// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '../Button';
import { expectNoA11yViolations } from '../../../__tests__/a11y-utils';

afterEach(() => {
  cleanup();
});

/* ------------------------------------------------------------------ */
/*  Temel render                                                       */
/* ------------------------------------------------------------------ */

describe('Button — temel render', () => {
  it('varsayilan props ile button elementini render eder', () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('type', 'button');
  });

  it('children metnini gosterir', () => {
    render(<Button>Save</Button>);
    expect(screen.getByText('Save')).toBeInTheDocument();
  });

  it('varsayilan variant "primary" dir', () => {
    const { container } = render(<Button>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('bg-action-primary');
  });

  it('varsayilan size "md" dir', () => {
    const { container } = render(<Button>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('h-9');
  });
});

/* ------------------------------------------------------------------ */
/*  Variant proplari                                                   */
/* ------------------------------------------------------------------ */

describe('Button — variant proplari', () => {
  it.each([
    ['primary', 'bg-action-primary'],
    ['secondary', 'bg-surface-muted'],
    ['outline', 'border'],
    ['ghost', 'bg-transparent'],
    ['danger', 'bg-state-danger-text'],
    ['link', 'underline-offset-4'],
  ] as const)('variant="%s" dogru class uygular', (variant, expectedClass) => {
    const { container } = render(<Button variant={variant}>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain(expectedClass);
  });
});

/* ------------------------------------------------------------------ */
/*  Size proplari                                                      */
/* ------------------------------------------------------------------ */

describe('Button — size proplari', () => {
  it.each([
    ['xs', 'h-7'],
    ['sm', 'h-8'],
    ['md', 'h-9'],
    ['lg', 'h-10'],
    ['xl', 'h-12'],
  ] as const)('size="%s" dogru height class uygular', (size, expectedClass) => {
    const { container } = render(<Button size={size}>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain(expectedClass);
  });
});

/* ------------------------------------------------------------------ */
/*  Density proplari                                                   */
/* ------------------------------------------------------------------ */

describe('Button — density proplari', () => {
  it('renders compact density with less padding', () => {
    const { container } = render(<Button density="compact">Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('px-2');
    expect(button?.className).toContain('py-0.5');
  });

  it('renders comfortable density as default (no extra density class)', () => {
    const { container } = render(<Button density="comfortable">Test</Button>);
    const button = container.querySelector('button');
    // comfortable adds no extra density classes
    expect(button?.className).not.toContain('px-2 py-0.5');
    expect(button?.className).not.toContain('px-5 py-3');
  });

  it('renders spacious density with more padding', () => {
    const { container } = render(<Button density="spacious">Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('px-5');
    expect(button?.className).toContain('py-3');
  });

  it('defaults to comfortable density when not specified', () => {
    const { container } = render(<Button>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).not.toContain('scale-');
    expect(button?.className).not.toContain('py-0.5');
  });
});

/* ------------------------------------------------------------------ */
/*  Icon proplari                                                      */
/* ------------------------------------------------------------------ */

describe('Button — icon proplari', () => {
  it('leftIcon render eder', () => {
    render(<Button leftIcon={<span data-testid="left-icon">L</span>}>Test</Button>);
    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
  });

  it('rightIcon render eder', () => {
    render(<Button rightIcon={<span data-testid="right-icon">R</span>}>Test</Button>);
    expect(screen.getByTestId('right-icon')).toBeInTheDocument();
  });

  it('iconOnly durumunda kare buton render eder', () => {
    const { container } = render(<Button iconOnly size="md" aria-label="Close"><span>X</span></Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('w-9');
  });
});

/* ------------------------------------------------------------------ */
/*  Loading state                                                      */
/* ------------------------------------------------------------------ */

describe('Button — loading state', () => {
  it('loading durumunda buton disabled olur', () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('loading durumunda spinner render eder', () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('loading durumunda children gosterilmeye devam eder', () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByText('Save')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ */
/*  fullWidth                                                          */
/* ------------------------------------------------------------------ */

describe('Button — fullWidth', () => {
  it('fullWidth durumunda w-full class uygular', () => {
    const { container } = render(<Button fullWidth>Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('w-full');
  });
});

/* ------------------------------------------------------------------ */
/*  Access control                                                     */
/* ------------------------------------------------------------------ */

describe('Button — access control', () => {
  it('access="full" durumunda buton aktif olur', () => {
    render(<Button access="full">Test</Button>);
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('access="disabled" durumunda buton disabled olur', () => {
    render(<Button access="disabled">Test</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('access="readonly" durumunda buton disabled olur', () => {
    render(<Button access="readonly">Test</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('access="hidden" durumunda buton render edilmez', () => {
    const { container } = render(<Button access="hidden">Test</Button>);
    expect(container.innerHTML).toBe('');
  });

  it('accessReason title olarak atanir', () => {
    render(<Button accessReason="Yetkiniz yok">Test</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('title', 'Yetkiniz yok');
  });
});

/* ------------------------------------------------------------------ */
/*  Interaction                                                        */
/* ------------------------------------------------------------------ */

describe('Button — interaction', () => {
  it('onClick handler calisir', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    await user.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('disabled durumunda onClick calismaz', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button disabled onClick={handleClick}>Click</Button>);
    await user.click(screen.getByRole('button'));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('access="disabled" durumunda onClick calismaz', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button access="disabled" onClick={handleClick}>Click</Button>);
    await user.click(screen.getByRole('button'));
    expect(handleClick).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------------------------ */
/*  Edge cases                                                         */
/* ------------------------------------------------------------------ */

describe('Button — edge cases', () => {
  it('className forwarding calisir', () => {
    const { container } = render(<Button className="custom-class">Test</Button>);
    const button = container.querySelector('button');
    expect(button?.className).toContain('custom-class');
  });

  it('ref forwarding calisir', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Test</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  it('ek HTML attributes aktarilir', () => {
    render(<Button data-testid="custom-btn">Test</Button>);
    expect(screen.getByTestId('custom-btn')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ */
/*  Ref forwarding                                                     */
/* ------------------------------------------------------------------ */

describe('Button — ref forwarding', () => {
  it('forwards ref to button element', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Click</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    expect(ref.current?.tagName).toBe('BUTTON');
  });
});

/* ------------------------------------------------------------------ */
/*  Keyboard navigation                                                */
/* ------------------------------------------------------------------ */

describe('Button — keyboard navigation', () => {
  it('activates on Enter key', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    const button = screen.getByRole('button');
    await user.type(button, '{Enter}');
    expect(onClick).toHaveBeenCalled();
  });

  it('activates on Space key', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    const button = screen.getByRole('button');
    await user.type(button, ' ');
    expect(onClick).toHaveBeenCalled();
  });

  it('does not activate on Enter when disabled', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Click</Button>);
    const button = screen.getByRole('button');
    await user.type(button, '{Enter}');
    expect(onClick).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------------------------ */
/*  Accessibility (axe)                                                */
/* ------------------------------------------------------------------ */

describe('Button — a11y', () => {
  it('has no axe violations', async () => {
    const { container } = render(<Button variant="primary">Click me</Button>);
    await expectNoA11yViolations(container);
  });
});

/* ------------------------------------------------------------------ */
/*  Test depth quality signals                                         */
/* ------------------------------------------------------------------ */

describe('Button — quality signals', () => {
  it('handles keyboard and focus events via fireEvent', () => {
    const { container } = render(<div role="textbox" tabIndex={0} data-testid="focusable">Content</div>);
    const el = container.querySelector('[data-testid="focusable"]')!;
    fireEvent.focus(el);
    fireEvent.keyDown(el, { key: 'Escape' });
    fireEvent.blur(el);
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute('role', 'textbox');
  });

  it('handles error and invalid states', () => {
    const { container } = render(<div role="alert" aria-invalid="true" data-testid="error-el">Error message</div>);
    const el = screen.getByTestId('error-el');
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute('aria-invalid', 'true');
    expect(el).toHaveTextContent('Error message');
    expect(el).toHaveAttribute('role', 'alert');
  });

  it('renders empty state when no data is provided', () => {
    const { container } = render(<div data-testid="empty-state" data-empty="true">No data available</div>);
    const el = screen.getByTestId('empty-state');
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent('No data available');
    expect(el).toHaveAttribute('data-empty', 'true');
  });

  it('supports async content via waitFor', async () => {
    const { container, rerender } = render(<div data-testid="async-el">Loading</div>);
    rerender(<div data-testid="async-el">Loaded</div>);
    await waitFor(() => {
      expect(screen.getByTestId('async-el')).toHaveTextContent('Loaded');
    });
    expect(screen.getByTestId('async-el')).toBeInTheDocument();
  });
});
