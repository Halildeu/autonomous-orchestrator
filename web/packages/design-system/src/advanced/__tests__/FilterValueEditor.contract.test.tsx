// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { FilterValueEditor } from '../data-grid/filter-builder/FilterValueEditor';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('FilterValueEditor — contract', () => {
  describe('text type', () => {
    it('renders text input and calls onChange on typing', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      render(
        <FilterValueEditor
          filterType="text"
          operator="contains"
          value=""
          onChange={onChange}
        />,
      );

      const input = screen.getByPlaceholderText('Değer girin...');
      await user.type(input, 'hello');
      expect(onChange).toHaveBeenCalled();
      // Each keystroke fires onChange
      expect(onChange.mock.calls.length).toBe(5);
    });

    it('displays current value in text input', () => {
      render(
        <FilterValueEditor
          filterType="text"
          operator="contains"
          value="existing"
          onChange={vi.fn()}
        />,
      );

      const input = screen.getByPlaceholderText('Değer girin...') as HTMLInputElement;
      expect(input.value).toBe('existing');
    });

    it('shows "no value needed" for blank operator', () => {
      render(
        <FilterValueEditor
          filterType="text"
          operator="blank"
          value=""
          onChange={vi.fn()}
        />,
      );

      expect(screen.getByText('Değer gerekmiyor')).toBeInTheDocument();
    });
  });

  describe('number type', () => {
    it('renders number input and calls onChange with numeric value', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      render(
        <FilterValueEditor
          filterType="number"
          operator="equals"
          value={null}
          onChange={onChange}
        />,
      );

      const input = screen.getByPlaceholderText('Değer');
      await user.type(input, '42');
      expect(onChange).toHaveBeenCalled();
    });

    it('renders range inputs for inRange operator', () => {
      render(
        <FilterValueEditor
          filterType="number"
          operator="inRange"
          value={10}
          valueTo={20}
          onChange={vi.fn()}
        />,
      );

      expect(screen.getByPlaceholderText('Başlangıç')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Bitiş')).toBeInTheDocument();
    });
  });

  describe('date type', () => {
    it('renders date input', () => {
      render(
        <FilterValueEditor
          filterType="date"
          operator="equals"
          value=""
          onChange={vi.fn()}
        />,
      );

      const input = screen.getByDisplayValue('');
      expect(input).toHaveAttribute('type', 'date');
    });

    it('renders two date inputs for inRange operator', () => {
      render(
        <FilterValueEditor
          filterType="date"
          operator="inRange"
          value="2024-01-01 00:00:00"
          valueTo="2024-12-31 23:59:59"
          onChange={vi.fn()}
        />,
      );

      const dateInputs = screen.getAllByDisplayValue(/2024/);
      expect(dateInputs.length).toBe(2);
    });
  });

  describe('set type', () => {
    it('renders checkboxes for set values', () => {
      render(
        <FilterValueEditor
          filterType="set"
          operator="in"
          value={[]}
          setValues={['Active', 'Inactive', 'Pending']}
          onChange={vi.fn()}
        />,
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes.length).toBe(3);
    });

    it('calls onChange with updated selection when checkbox toggled', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      render(
        <FilterValueEditor
          filterType="set"
          operator="in"
          value={[]}
          setValues={['Active', 'Inactive']}
          onChange={onChange}
        />,
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);
      expect(onChange).toHaveBeenCalledWith(['Active']);
    });

    it('shows selected count and allows removing individual values', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();

      render(
        <FilterValueEditor
          filterType="set"
          operator="in"
          value={['Active', 'Pending']}
          setValues={['Active', 'Inactive', 'Pending']}
          onChange={onChange}
        />,
      );

      // Remove buttons appear for selected values
      const removeButtons = screen.getAllByText('×');
      expect(removeButtons.length).toBe(2);

      await user.click(removeButtons[0]);
      expect(onChange).toHaveBeenCalledWith(['Pending']);
    });
  });

  describe('disabled state', () => {
    it('disables text input when disabled prop is true', () => {
      render(
        <FilterValueEditor
          filterType="text"
          operator="contains"
          value=""
          disabled={true}
          onChange={vi.fn()}
        />,
      );

      const input = screen.getByPlaceholderText('Değer girin...');
      expect(input).toBeDisabled();
    });

    it('disables checkboxes in set type when disabled', () => {
      render(
        <FilterValueEditor
          filterType="set"
          operator="in"
          value={[]}
          setValues={['Active']}
          disabled={true}
          onChange={vi.fn()}
        />,
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeDisabled();
    });
  });
});
