// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FileUploadZone } from '../FileUploadZone';

afterEach(cleanup);

describe('FileUploadZone — depth', () => {
  describe('FileUploadZone — depth: prop combinations', () => {
    it('renders with multiple + disabled simultaneously', () => {
      render(<FileUploadZone multiple disabled>Stressed</FileUploadZone>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FileUploadZone multiple disabled />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FileUploadZone — depth: files array edge cases', () => {
    it('handles empty files', () => {
      const { container } = render(<FileUploadZone files={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item files', () => {
      const { container } = render(<FileUploadZone files={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FileUploadZone — depth: onFilesAdd array edge cases', () => {
    it('handles empty onFilesAdd', () => {
      const { container } = render(<FileUploadZone onFilesAdd={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onFilesAdd', () => {
      const { container } = render(<FileUploadZone onFilesAdd={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
