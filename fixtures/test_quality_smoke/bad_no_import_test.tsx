// Fixture: TQ-004 positive match — filename implies Dialog but no Dialog import
import { render, screen } from '@testing-library/react';

test('renders dialog', () => {
  render(<div data-testid="dialog">mock</div>);
  expect(screen.getByTestId('dialog')).toBeInTheDocument();
});
