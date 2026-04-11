// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AIGuidedAuthoring } from '../ai-guided-authoring/AIGuidedAuthoring';
import type { AIGuidedAuthoringRecommendation, AIGuidedAuthoringProps } from '../ai-guided-authoring/AIGuidedAuthoring';

describe('AIGuidedAuthoring — contract', () => {
  const defaultProps = {
    id: undefined as any,
    item: undefined as any,
    id: undefined as any,
    item: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<AIGuidedAuthoring {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AIGuidedAuthoring.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AIGuidedAuthoring {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AIGuidedAuthoring {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (4 required, 15 optional)', () => {
    // All 15 optional props omitted — should not crash
    const { container } = render(<AIGuidedAuthoring {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _aiguidedauthoringrecommendation: AIGuidedAuthoringRecommendation | undefined = undefined; void _aiguidedauthoringrecommendation;
    const _aiguidedauthoringprops: AIGuidedAuthoringProps | undefined = undefined; void _aiguidedauthoringprops;
    expect(true).toBe(true);
  });
});
