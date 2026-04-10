// Fixture: negative match — real test with interaction and behavioral assertions
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../Button';

test('button calls onClick when clicked', () => {
  const handleClick = vi.fn();
  render(<Button onClick={handleClick} label="Save" disabled={false} />);

  const button = screen.getByRole('button', { name: 'Save' });
  expect(button).toBeEnabled();

  fireEvent.click(button);
  expect(handleClick).toHaveBeenCalledTimes(1);
});

test('button shows loading state', () => {
  render(<Button loading={true} label="Submit" />);

  expect(screen.getByRole('button')).toBeDisabled();
  expect(screen.getByText('Loading...')).toBeVisible();
});
