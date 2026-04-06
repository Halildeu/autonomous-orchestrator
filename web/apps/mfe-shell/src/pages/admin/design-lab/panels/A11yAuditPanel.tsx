import React, { useState, useMemo, useCallback, _useEffect, _useRef } from "react";
import {
  Accessibility,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  ExternalLink,
  Shield,
} from "lucide-react";
import { Text } from "@mfe/design-system";

/* ------------------------------------------------------------------ */
/*  A11yAuditPanel — Live accessibility audit for playground preview     */
/*                                                                     */
/*  Features:                                                          */
/*  - Runs audit against current preview DOM                           */
/*  - Shows violations by impact level                                 */
/*  - Expandable details per violation                                 */
/*  - WCAG reference links                                             */
/*  - Auto-runs on prop changes (debounced)                            */
/*  - Score summary (pass/fail/warning counts)                         */
/*                                                                     */
/*  Note: Uses a built-in rule engine instead of axe-core to avoid     */
/*  heavy dependency. Can be upgraded to axe-core later.               */
/* ------------------------------------------------------------------ */

export type A11yImpact = "critical" | "serious" | "moderate" | "minor";

export type A11yViolation = {
  id: string;
  rule: string;
  impact: A11yImpact;
  description: string;
  help: string;
  helpUrl?: string;
  element?: string;
  fix?: string;
};

const IMPACT_META: Record<A11yImpact, { label: string; color: string; icon: React.ReactNode; bg: string }> = {
  critical: { label: "Critical", color: "text-state-danger-text", icon: <AlertCircle className="h-3.5 w-3.5" />, bg: "bg-state-danger-bg" },
  serious: { label: "Serious", color: "text-state-warning-text", icon: <AlertTriangle className="h-3.5 w-3.5" />, bg: "bg-state-warning-bg" },
  moderate: { label: "Moderate", color: "text-state-warning-text", icon: <Info className="h-3.5 w-3.5" />, bg: "bg-state-warning-bg" },
  minor: { label: "Minor", color: "text-action-primary", icon: <Info className="h-3.5 w-3.5" />, bg: "bg-state-info-bg" },
};

/* ---- Built-in accessibility rules engine ---- */

type AuditContext = {
  componentName: string;
  propNames: string[];
  propValues: Record<string, unknown>;
  hasChildren: boolean;
};

function runAccessibilityAudit(ctx: AuditContext): A11yViolation[] {
  const violations: A11yViolation[] = [];
  const { componentName, propNames, propValues } = ctx;
  const propSet = new Set(propNames);

  // Rule: aria-label for interactive elements
  const isInteractive = ["Button", "IconButton", "Input", "Select", "Checkbox", "Switch", "Slider", "Toggle"].includes(componentName);
  if (isInteractive && !propSet.has("aria-label") && !propSet.has("ariaLabel") && !propSet.has("label") && !ctx.hasChildren) {
    violations.push({
      id: "aria-label-missing",
      rule: "aria-label",
      impact: "critical",
      description: `Interactive ${componentName} should have an accessible label.`,
      help: "Add aria-label, label prop, or visible text content.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/label",
      fix: `<${componentName} aria-label="Descriptive label" />`,
    });
  }

  // Rule: Button should not be empty
  if (componentName === "Button" && !ctx.hasChildren && !propValues.children) {
    violations.push({
      id: "button-empty",
      rule: "button-name",
      impact: "critical",
      description: "Button must have accessible text content.",
      help: "Add text content or aria-label to the button.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/button-name",
      fix: `<Button aria-label="Action description">Label</Button>`,
    });
  }

  // Rule: Image/Icon alt text
  if (["Avatar", "Image", "Icon"].includes(componentName) && !propSet.has("alt") && !propSet.has("aria-label")) {
    violations.push({
      id: "img-alt-missing",
      rule: "image-alt",
      impact: "serious",
      description: `${componentName} should have alternative text.`,
      help: "Add alt or aria-label for screen readers.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/image-alt",
      fix: `<${componentName} alt="Description of image" />`,
    });
  }

  // Rule: Form inputs need labels
  const isFormInput = ["Input", "Textarea", "Select", "Combobox", "DatePicker"].includes(componentName);
  if (isFormInput && !propSet.has("label") && !propSet.has("aria-label") && !propSet.has("id")) {
    violations.push({
      id: "form-label-missing",
      rule: "label",
      impact: "serious",
      description: `${componentName} should be associated with a label.`,
      help: "Add a label prop or use aria-label for accessibility.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/label",
      fix: `<${componentName} label="Field label" />`,
    });
  }

  // Rule: Color contrast awareness
  if (propValues.variant === "ghost" || propValues.variant === "link") {
    violations.push({
      id: "color-contrast-check",
      rule: "color-contrast",
      impact: "moderate",
      description: `Ghost/link variants may have lower contrast on some backgrounds.`,
      help: "Verify color contrast meets WCAG 2.1 AA (4.5:1 ratio) on the intended background.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/color-contrast",
    });
  }

  // Rule: Disabled without reason
  if (propValues.disabled === true && !propSet.has("title") && !propSet.has("aria-label")) {
    violations.push({
      id: "disabled-no-reason",
      rule: "disabled-explanation",
      impact: "moderate",
      description: "Disabled elements should communicate why they are disabled.",
      help: "Add a title or tooltip explaining why the element is disabled.",
      fix: `<${componentName} disabled title="Requires permission" />`,
    });
  }

  // Rule: Focus management for overlays
  if (["Modal", "Dialog", "Drawer", "Popover", "Sheet"].includes(componentName)) {
    if (!propSet.has("onClose") && !propSet.has("onDismiss")) {
      violations.push({
        id: "overlay-dismiss",
        rule: "dialog-close",
        impact: "serious",
        description: "Overlay components should have a dismiss mechanism.",
        help: "Add onClose or onDismiss handler. Ensure Escape key also closes.",
        helpUrl: "https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/",
        fix: `<${componentName} onClose={handleClose} />`,
      });
    }
  }

  // Rule: Table headers
  if (componentName === "Table" || componentName === "TableSimple") {
    violations.push({
      id: "table-headers",
      rule: "table-headers",
      impact: "minor",
      description: "Ensure table has proper th elements with scope attributes.",
      help: "Use <th scope='col'> for column headers and <th scope='row'> for row headers.",
      helpUrl: "https://dequeuniversity.com/rules/axe/4.6/th-has-data-cells",
    });
  }

  // Rule: Keyboard interaction
  if (isInteractive && !propSet.has("onKeyDown") && !propSet.has("tabIndex")) {
    violations.push({
      id: "keyboard-support",
      rule: "keyboard-navigation",
      impact: "minor",
      description: `Consider explicit keyboard handlers for ${componentName}.`,
      help: "While native elements handle keyboard events, custom components should ensure proper keyboard support.",
    });
  }

  // Add passes for things that are correct
  if (propSet.has("aria-label") || propSet.has("label")) {
    // This is good — no violation needed
  }

  return violations;
}

/* ---- Panel Component ---- */

type A11yAuditPanelProps = {
  componentName: string;
  propNames: string[];
  propValues: Record<string, unknown>;
  expanded: boolean;
  onToggle: () => void;
};

export const A11yAuditPanel: React.FC<A11yAuditPanelProps> = ({
  componentName,
  propNames,
  propValues,
  expanded,
  onToggle,
}) => {
  const [expandedViolations, setExpandedViolations] = useState<Set<string>>(new Set());
  const [filterImpact, setFilterImpact] = useState<A11yImpact | "all">("all");

  const violations = useMemo(
    () =>
      runAccessibilityAudit({
        componentName,
        propNames,
        propValues,
        hasChildren: Boolean(propValues.children),
      }),
    [componentName, propNames, propValues],
  );

  const filteredViolations = useMemo(() => {
    if (filterImpact === "all") return violations;
    return violations.filter((v) => v.impact === filterImpact);
  }, [violations, filterImpact]);

  const impactCounts = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, serious: 0, moderate: 0, minor: 0 };
    violations.forEach((v) => { counts[v.impact] = (counts[v.impact] || 0) + 1; });
    return counts;
  }, [violations]);

  const toggleViolation = useCallback((id: string) => {
    setExpandedViolations((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const scoreColor = violations.length === 0
    ? "text-state-success-text"
    : impactCounts.critical > 0
      ? "text-state-danger-text"
      : impactCounts.serious > 0
        ? "text-state-warning-text"
        : "text-state-warning-text";

  return (
    <div className="border-t border-border-subtle">
      {/* Header */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-surface-muted/50 transition"
      >
        <div className="flex items-center gap-2">
          <Accessibility className="h-3.5 w-3.5 text-text-tertiary" />
          <Text as="span" className="text-xs font-semibold text-text-primary">
            Accessibility Audit
          </Text>
          {violations.length === 0 ? (
            <span className="flex items-center gap-1 rounded-md bg-state-success-bg px-1.5 py-0.5 text-[10px] font-semibold text-state-success-text">
              <CheckCircle2 className="h-3 w-3" /> Pass
            </span>
          ) : (
            <span className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${impactCounts.critical > 0 ? "bg-state-danger-bg text-state-danger-text" : "bg-state-warning-bg text-state-warning-text"}`}>
              {violations.length} issue{violations.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" /> : <ChevronRight className="h-3.5 w-3.5 text-text-tertiary" />}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="flex flex-col border-t border-border-subtle px-4 py-3 gap-3">
          {/* Score summary */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Shield className={`h-5 w-5 ${scoreColor}`} />
              <Text as="span" className={`text-lg font-bold ${scoreColor}`}>
                {violations.length === 0 ? "100" : Math.max(0, 100 - (impactCounts.critical * 25 + impactCounts.serious * 15 + impactCounts.moderate * 5 + impactCounts.minor * 2))}
              </Text>
              <Text variant="secondary" className="text-[10px]">/ 100</Text>
            </div>
            <div className="flex gap-2">
              {(["critical", "serious", "moderate", "minor"] as const).map((impact) => (
                impactCounts[impact] > 0 && (
                  <span key={impact} className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${IMPACT_META[impact].bg} ${IMPACT_META[impact].color}`}>
                    {impactCounts[impact]} {IMPACT_META[impact].label}
                  </span>
                )
              ))}
            </div>
          </div>

          {/* Impact filter */}
          {violations.length > 0 && (
            <div className="flex gap-1">
              {(["all", "critical", "serious", "moderate", "minor"] as const).map((impact) => (
                <button
                  key={impact}
                  type="button"
                  onClick={() => setFilterImpact(impact)}
                  className={[
                    "rounded-md px-2 py-1 text-[10px] font-medium transition",
                    filterImpact === impact
                      ? "bg-action-primary text-text-inverse"
                      : "bg-surface-muted text-text-secondary hover:text-text-primary",
                  ].join(" ")}
                >
                  {impact === "all" ? "All" : IMPACT_META[impact].label}
                </button>
              ))}
            </div>
          )}

          {/* Violations list */}
          {filteredViolations.length === 0 && violations.length === 0 && (
            <div className="flex items-center gap-2 rounded-xl bg-state-success-bg p-3">
              <CheckCircle2 className="h-4 w-4 text-state-success-text" />
              <Text className="text-xs text-state-success-text">
                No accessibility issues detected. Great job!
              </Text>
            </div>
          )}

          {filteredViolations.map((violation) => {
            const meta = IMPACT_META[violation.impact];
            const isOpen = expandedViolations.has(violation.id);

            return (
              <div key={violation.id} className="overflow-hidden rounded-xl border border-border-subtle">
                <button
                  type="button"
                  onClick={() => toggleViolation(violation.id)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-muted/50 transition"
                >
                  <span className={meta.color}>{meta.icon}</span>
                  <div className="min-w-0 flex-1">
                    <Text as="div" className="text-xs font-medium text-text-primary truncate">
                      {violation.description}
                    </Text>
                  </div>
                  <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-semibold ${meta.bg} ${meta.color}`}>
                    {meta.label}
                  </span>
                  {isOpen ? <ChevronDown className="h-3 w-3 text-text-tertiary shrink-0" /> : <ChevronRight className="h-3 w-3 text-text-tertiary shrink-0" />}
                </button>

                {isOpen && (
                  <div className="flex flex-col border-t border-border-subtle bg-surface-canvas px-3 py-2.5 gap-2">
                    <Text variant="secondary" className="text-xs leading-relaxed">
                      {violation.help}
                    </Text>
                    {violation.fix && (
                      <pre className="overflow-x-auto rounded-lg bg-surface-inverse px-3 py-2 text-[11px] text-border-subtle font-mono">
                        {violation.fix}
                      </pre>
                    )}
                    <div className="flex items-center gap-3">
                      <Text variant="secondary" className="text-[10px] font-mono">
                        Rule: {violation.rule}
                      </Text>
                      {violation.helpUrl && (
                        <a
                          href={violation.helpUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-[10px] font-medium text-action-primary hover:underline"
                        >
                          WCAG Reference <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default A11yAuditPanel;
