// Fixture: EP-006 positive match — shallow render with existence-only assertion
import { render, screen } from '@testing-library/react';
import { Button } from '../Button';

test('renders button', () => {
  render(<Button />);
  expect(screen.getByTestId('btn')).toBeInTheDocument();
});
