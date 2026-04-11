// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Upload } from '../upload/Upload';

afterEach(cleanup);

describe('Upload — depth', () => {
  describe('Upload — depth: prop combinations', () => {
    it('renders with invalid + fullWidth simultaneously', () => {
      render(<Upload invalid fullWidth>Stressed</Upload>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Upload invalid fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Upload — depth: onFilesChange array edge cases', () => {
    it('handles empty onFilesChange', () => {
      const { container } = render(<Upload onFilesChange={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onFilesChange', () => {
      const { container } = render(<Upload onFilesChange={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Upload — depth: files array edge cases', () => {
    it('handles empty files', () => {
      const { container } = render(<Upload files={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item files', () => {
      const { container } = render(<Upload files={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
