import React from 'react';
import { withConditionalFormatting } from './conditional';
import type { ConditionalRule } from './types';

export default {
  title: 'Advanced/Column System/Conditional Formatting',
  parameters: { layout: 'padded' },
};

const rules: ConditionalRule[] = [
  { condition: 'gt', threshold: 90, badgeVariant: 'success' },
  { condition: 'lt', threshold: 50, textColor: '#ef4444', bgColor: '#fef2f2' },
];

export const WithRules = () => {
  const render = withConditionalFormatting(undefined, rules);
  return (
    <div className="flex flex-col gap-3">
      {[95, 72, 30, null].map((val, i) => (
        <div key={i} className="flex items-center gap-4">
          <span className="w-20 text-xs text-text-secondary">value={String(val)}</span>
          <div className="rounded border border-border-subtle bg-surface-default p-2">
            {render({ value: val, data: {} })}
          </div>
        </div>
      ))}
    </div>
  );
};
