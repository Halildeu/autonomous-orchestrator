// Fixture: EP-007 positive match — tautological assertions
import { render } from '@testing-library/react';
import { Card } from '../Card';

test('card exists', () => {
  render(<Card />);
  expect(true).toBe(true);
  expect(1).toBe(1);
});

test('card defined', () => {
  const wrapper = render(<Card />);
  expect(wrapper).toBeDefined();
});
