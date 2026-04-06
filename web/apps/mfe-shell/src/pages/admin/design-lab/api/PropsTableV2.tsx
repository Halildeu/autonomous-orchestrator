import React, { useState, useMemo, _useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink as _ExternalLink,
  Zap,
  Search,
  Filter as _Filter,
} from "lucide-react";
import { Text } from "@mfe/design-system";
import { CodeBlock } from "../../../../../../../packages/design-system/src/catalog/design-lab-internals";

/* ------------------------------------------------------------------ */
/*  PropsTableV2 — Rich API reference table                            */
/*                                                                     */
/*  Surpasses MUI/AntD API tables with:                                */
/*  - Expandable rows with type tree + inline code examples            */
/*  - Clickable union/enum chips                                       */
/*  - Search and filter (required, optional, deprecated)               */
/*  - TypeScript type tree renderer for complex types                  */
/* ------------------------------------------------------------------ */

type ApiProp = {
  name: string;
  type: string;
  default: string;
  required: boolean;
  description: string;
};

type PropsTableV2Props = {
  props: ApiProp[];
  componentName: string;
  onTryValue?: (propName: string, value: string) => void;
};

/* ---- Type parsing utilities ---- */

function parseUnionType(typeStr: string): string[] | null {
  // Match simple union types like "'primary' | 'secondary' | 'ghost'"
  const cleaned = typeStr.trim();
  if (!cleaned.includes("|")) return null;

  const parts = cleaned.split("|").map((p) => p.trim());
  // Only treat as union if all parts are simple string literals or identifiers
  const isSimpleUnion = parts.every(
    (p) => /^'[^']*'$/.test(p) || /^"[^"]*"$/.test(p) || /^[a-zA-Z_]\w*$/.test(p) || /^\d+$/.test(p)
  );
  if (!isSimpleUnion) return null;
  return parts.map((p) => p.replace(/^['"]|['"]$/g, ""));
}

function isComplexType(typeStr: string): boolean {
  return (
    typeStr.includes("=>") ||
    typeStr.includes("ReactNode") ||
    typeStr.includes("React.") ||
    typeStr.includes("{") ||
    typeStr.includes("Record<") ||
    typeStr.includes("Array<") ||
    typeStr.length > 60
  );
}

function getTypeBadgeColor(typeStr: string): string {
  if (typeStr === "boolean") return "bg-state-warning-bg text-state-warning-text";
  if (typeStr === "string") return "bg-state-success-bg text-state-success-text";
  if (typeStr === "number") return "bg-state-info-bg text-state-info-text";
  if (typeStr.includes("|")) return "bg-action-primary/10 text-action-primary";
  if (typeStr.includes("=>") || typeStr.includes("Function")) return "bg-state-danger-bg text-state-danger-text";
  if (typeStr.includes("React")) return "bg-action-primary/10 text-action-primary";
  return "bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

/* ---- Union Chip ---- */

function UnionChip({
  value,
  onClick,
}: {
  value: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-mono font-medium transition",
        onClick
          ? "bg-action-primary/10 text-action-primary hover:bg-action-primary/10 cursor-pointer"
          : "bg-surface-muted text-text-secondary",
      ].join(" ")}
      title={onClick ? `Set playground to "${value}"` : undefined}
    >
      {value}
    </button>
  );
}

/* ---- Type Tree Renderer (for complex types) ---- */

function TypeTreeView({ typeStr }: { typeStr: string }) {
  // Simple expandable code view for complex types
  return (
    <div className="mt-2 rounded-lg bg-surface-canvas p-3">
      <pre className="text-[11px] font-mono text-text-secondary whitespace-pre-wrap break-all leading-5">
        {formatTypeString(typeStr)}
      </pre>
    </div>
  );
}

function formatTypeString(typeStr: string): string {
  // Basic formatting: add newlines after { and before }, indent
  let depth = 0;
  let result = "";
  for (let i = 0; i < typeStr.length; i++) {
    const ch = typeStr[i];
    if (ch === "{" || ch === "[") {
      depth++;
      result += ch + "\n" + "  ".repeat(depth);
    } else if (ch === "}" || ch === "]") {
      depth--;
      result += "\n" + "  ".repeat(depth) + ch;
    } else if (ch === ";" || (ch === "," && depth > 0)) {
      result += ch + "\n" + "  ".repeat(depth);
    } else {
      result += ch;
    }
  }
  return result;
}

/* ---- Generate example for a prop ---- */

function generatePropExample(prop: ApiProp, componentName: string): string | null {
  const unionValues = parseUnionType(prop.type);
  if (unionValues && unionValues.length > 1) {
    const examples = unionValues.slice(0, 3).map(
      (v) => `<${componentName} ${prop.name}="${v}" />`
    );
    return examples.join("\n");
  }
  if (prop.type === "boolean") {
    return `<${componentName} ${prop.name} />\n<${componentName} ${prop.name}={false} />`;
  }
  if (prop.type === "string") {
    return `<${componentName} ${prop.name}="custom value" />`;
  }
  if (prop.type === "number") {
    return `<${componentName} ${prop.name}={42} />`;
  }
  return null;
}

/* ---- Prop Row ---- */

function PropRow({
  prop,
  componentName,
  isExpanded,
  onToggle,
  onTryValue,
}: {
  prop: ApiProp;
  componentName: string;
  isExpanded: boolean;
  onToggle: () => void;
  onTryValue?: (propName: string, value: string) => void;
}) {
  const unionValues = parseUnionType(prop.type);
  const complex = isComplexType(prop.type);
  const typeBadge = getTypeBadgeColor(prop.type);
  const example = useMemo(() => generatePropExample(prop, componentName), [prop, componentName]);

  return (
    <>
      <tr
        className="group border-b border-border-subtle transition-colors last:border-0 hover:bg-surface-canvas/30 cursor-pointer"
        onClick={onToggle}
      >
        {/* Expand chevron + name */}
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-text-tertiary">
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </span>
            <code className="rounded-md bg-surface-canvas px-1.5 py-0.5 font-mono text-xs font-semibold text-text-primary">
              {prop.name}
            </code>
            {prop.required && (
              <span className="rounded-xs bg-state-warning-text/10 px-1 py-0.5 text-[9px] font-bold uppercase text-state-warning-text">
                req
              </span>
            )}
          </div>
        </td>

        {/* Type */}
        <td className="px-4 py-3">
          {unionValues ? (
            <div className="flex flex-wrap gap-1">
              {unionValues.slice(0, 4).map((v) => (
                <UnionChip
                  key={v}
                  value={v}
                  onClick={onTryValue ? () => onTryValue(prop.name, v) : undefined}
                />
              ))}
              {unionValues.length > 4 && (
                <span className="text-[10px] text-text-tertiary">
                  +{unionValues.length - 4} more
                </span>
              )}
            </div>
          ) : (
            <span className={["inline-flex rounded-md px-2 py-0.5 text-[11px] font-mono font-medium", typeBadge].join(" ")}>
              {prop.type.length > 30 ? prop.type.slice(0, 30) + "…" : prop.type}
            </span>
          )}
        </td>

        {/* Default */}
        <td className="px-4 py-3">
          <code className="font-mono text-xs text-text-secondary">
            {prop.default || "—"}
          </code>
        </td>

        {/* Description */}
        <td className="max-w-[300px] px-4 py-3 text-xs leading-5 text-text-secondary">
          {prop.description}
        </td>
      </tr>

      {/* Expanded detail row */}
      {isExpanded && (
        <tr className="border-b border-border-subtle bg-surface-canvas/20">
          <td colSpan={4} className="px-6 py-4">
            <div className="flex flex-col gap-3">
              {/* Full type display for complex types */}
              {complex && (
                <div>
                  <Text className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                    Full Type
                  </Text>
                  <TypeTreeView typeStr={prop.type} />
                </div>
              )}

              {/* Inline example */}
              {example && (
                <div>
                  <Text className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                    Usage Example
                  </Text>
                  <CodeBlock
                    code={example}
                    language="tsx"
                    variant="dark"
                    className="rounded-lg!"
                  />
                </div>
              )}

              {/* Quick try for union types */}
              {unionValues && onTryValue && (
                <div>
                  <Text className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                    Try in Playground
                  </Text>
                  <div className="flex flex-wrap gap-1.5">
                    {unionValues.map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => onTryValue(prop.name, v)}
                        className="flex items-center gap-1 rounded-lg bg-action-primary/10 px-2.5 py-1 text-[11px] font-medium text-action-primary transition hover:bg-action-primary/20"
                      >
                        <Zap className="h-2.5 w-2.5" />
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ==================================================================== */
/*  Main Component                                                       */
/* ==================================================================== */

type FilterMode = "all" | "required" | "optional";

export const PropsTableV2: React.FC<PropsTableV2Props> = ({
  props,
  componentName,
  onTryValue,
}) => {
  const [expandedProp, setExpandedProp] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");

  const filteredProps = useMemo(() => {
    let result = props;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.type.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q)
      );
    }
    if (filter === "required") result = result.filter((p) => p.required);
    if (filter === "optional") result = result.filter((p) => !p.required);
    return result;
  }, [props, search, filter]);

  const requiredCount = props.filter((p) => p.required).length;
  const optionalCount = props.length - requiredCount;

  return (
    <div className="flex flex-col gap-3">
      {/* Search + Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search props…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-border-subtle bg-surface-default pl-9 pr-3 py-2 text-xs text-text-primary outline-hidden placeholder:text-text-tertiary focus:border-action-primary"
          />
        </div>
        <div className="flex gap-1">
          {([
            { id: "all" as const, label: "All", count: props.length },
            { id: "required" as const, label: "Required", count: requiredCount },
            { id: "optional" as const, label: "Optional", count: optionalCount },
          ] as const).map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setFilter(opt.id)}
              className={[
                "flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition",
                filter === opt.id
                  ? "bg-action-primary text-text-inverse"
                  : "bg-surface-muted text-text-secondary hover:text-text-primary",
              ].join(" ")}
            >
              {opt.label}
              <span className={filter === opt.id ? "text-text-inverse/70" : "text-text-tertiary"}>
                {opt.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-surface-canvas/50 text-left">
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                  Prop
                </th>
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                  Type
                </th>
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                  Default
                </th>
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredProps.map((prop) => (
                <PropRow
                  key={prop.name}
                  prop={prop}
                  componentName={componentName}
                  isExpanded={expandedProp === prop.name}
                  onToggle={() =>
                    setExpandedProp((prev) =>
                      prev === prop.name ? null : prop.name
                    )
                  }
                  onTryValue={onTryValue}
                />
              ))}
              {filteredProps.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center">
                    <Text variant="secondary" className="text-xs">
                      No props match "{search}"
                    </Text>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PropsTableV2;
