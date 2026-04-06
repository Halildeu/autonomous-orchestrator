import React, { useState, useCallback, useMemo } from "react";
import {
  Plus,
  Trash2,
  Copy,
  Check,
  Download,
  Code2,
  Grid3X3,
  AlignHorizontalSpaceAround,
  AlignVerticalSpaceAround,
  Search,
  Save,
  FolderOpen,
  X,
  Move,
} from "lucide-react";
import { Text } from "@mfe/design-system";
import { PlaygroundPreview } from "../playground/PlaygroundPreview";
import { PreviewThemeWrapper } from "../playground/PreviewThemeWrapper";
import { exportToReact, exportToClipboard } from "./composeExporter";
import type { CanvasNode, LayoutConfig } from "./composeExporter";

/* ------------------------------------------------------------------ */
/*  ComposePage — Visual Composition Builder (full-page)               */
/*                                                                     */
/*  Features:                                                          */
/*  - Component palette with search                                    */
/*  - Canvas with click-to-place components                            */
/*  - Layout mode: flex row/column or CSS grid                         */
/*  - Per-component inline props editor                                */
/*  - Export as React component file                                   */
/*  - Save/load compositions (localStorage)                            */
/*                                                                     */
/*  Unique: No competitor has a visual composition builder.             */
/* ------------------------------------------------------------------ */

const PALETTE_COMPONENTS = [
  { name: "Button", defaults: { children: "Click me", variant: "primary" } },
  { name: "Input", defaults: { placeholder: "Enter text..." } },
  { name: "Select", defaults: { placeholder: "Choose..." } },
  { name: "Checkbox", defaults: { children: "Check me" } },
  { name: "Switch", defaults: {} },
  { name: "Badge", defaults: { children: "Badge" } },
  { name: "Alert", defaults: { children: "Alert message", variant: "info" } },
  { name: "Avatar", defaults: {} },
  { name: "Divider", defaults: {} },
  { name: "Text", defaults: { children: "Sample text" } },
  { name: "Tooltip", defaults: { children: "Hover me" } },
  { name: "Skeleton", defaults: {} },
];

const STORAGE_KEY = "designlab_compositions";

type SavedComposition = {
  id: string;
  name: string;
  nodes: CanvasNode[];
  layout: LayoutConfig;
  savedAt: string;
};

function loadCompositions(): SavedComposition[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveCompositions(list: SavedComposition[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

export default function ComposePage() {
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [layout, setLayout] = useState<LayoutConfig>({ type: "flex", direction: "column", gap: 4 });
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);
  const [paletteSearch, setPaletteSearch] = useState("");
  const [showLibrary, setShowLibrary] = useState(false);
  const [compositions, setCompositions] = useState<SavedComposition[]>(loadCompositions);

  const filteredPalette = useMemo(() => {
    if (!paletteSearch) return PALETTE_COMPONENTS;
    const q = paletteSearch.toLowerCase();
    return PALETTE_COMPONENTS.filter((c) => c.name.toLowerCase().includes(q));
  }, [paletteSearch]);

  const selectedNode = nodes.find((n) => n.id === selectedId);

  const addComponent = useCallback((name: string, defaults: Record<string, unknown>) => {
    const id = `node-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newNode: CanvasNode = {
      id,
      componentName: name,
      props: { ...defaults },
      x: 0,
      y: 0,
      w: 200,
      h: 40,
    };
    setNodes((prev) => [...prev, newNode]);
    setSelectedId(id);
  }, []);

  const removeNode = useCallback((id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id));
    if (selectedId === id) setSelectedId(null);
  }, [selectedId]);

  const updateNodeProp = useCallback((id: string, key: string, value: unknown) => {
    setNodes((prev) =>
      prev.map((n) => (n.id === id ? { ...n, props: { ...n.props, [key]: value } } : n)),
    );
  }, []);

  const moveNode = useCallback((id: string, direction: "up" | "down") => {
    setNodes((prev) => {
      const idx = prev.findIndex((n) => n.id === id);
      if (idx === -1) return prev;
      const targetIdx = direction === "up" ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[targetIdx]] = [next[targetIdx], next[idx]];
      return next;
    });
  }, []);

  const exportedCode = useMemo(
    () => exportToReact(nodes, layout),
    [nodes, layout],
  );

  const handleCopy = useCallback(async () => {
    await exportToClipboard(exportedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [exportedCode]);

  const handleSave = useCallback(() => {
    const name = `Composition ${compositions.length + 1}`;
    const comp: SavedComposition = {
      id: `comp-${Date.now()}`,
      name,
      nodes,
      layout,
      savedAt: new Date().toISOString(),
    };
    const updated = [comp, ...compositions];
    setCompositions(updated);
    saveCompositions(updated);
  }, [nodes, layout, compositions]);

  const handleLoad = useCallback((comp: SavedComposition) => {
    setNodes(comp.nodes);
    setLayout(comp.layout);
    setShowLibrary(false);
    setSelectedId(null);
  }, []);

  const handleDeleteComposition = useCallback((id: string) => {
    const updated = compositions.filter((c) => c.id !== id);
    setCompositions(updated);
    saveCompositions(updated);
  }, [compositions]);

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4">
      {/* Left: Palette */}
      <div className="flex w-52 shrink-0 flex-col rounded-2xl border border-border-subtle bg-surface-default">
        <div className="border-b border-border-subtle px-3 py-2">
          <Text as="div" className="text-xs font-semibold text-text-primary mb-2">Components</Text>
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-text-tertiary" />
            <input
              type="text"
              value={paletteSearch}
              onChange={(e) => setPaletteSearch(e.target.value)}
              placeholder="Search..."
              className="w-full rounded-md border border-border-subtle bg-surface-canvas pl-7 pr-2 py-1 text-[11px] outline-hidden focus:border-action-primary"
            />
          </div>
        </div>
        <div className="flex flex-col flex-1 overflow-y-auto p-2 gap-0.5">
          {filteredPalette.map((comp) => (
            <button
              key={comp.name}
              type="button"
              onClick={() => addComponent(comp.name, comp.defaults)}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[11px] font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary transition"
            >
              <Plus className="h-3 w-3 shrink-0 text-text-tertiary" />
              {comp.name}
            </button>
          ))}
        </div>
        <div className="flex flex-col border-t border-border-subtle p-2 gap-1">
          <button
            type="button"
            onClick={handleSave}
            disabled={nodes.length === 0}
            className="flex w-full items-center gap-2 rounded-lg bg-action-primary/10 px-2.5 py-1.5 text-[11px] font-medium text-action-primary hover:bg-action-primary/20 transition disabled:opacity-50"
          >
            <Save className="h-3 w-3" /> Save
          </button>
          <button
            type="button"
            onClick={() => setShowLibrary(!showLibrary)}
            className="flex w-full items-center gap-2 rounded-lg bg-surface-muted px-2.5 py-1.5 text-[11px] font-medium text-text-secondary hover:text-text-primary transition"
          >
            <FolderOpen className="h-3 w-3" /> Library ({compositions.length})
          </button>
        </div>
      </div>

      {/* Center: Canvas */}
      <div className="flex flex-1 flex-col gap-3">
        {/* Layout controls */}
        <div className="flex items-center gap-2 rounded-xl border border-border-subtle bg-surface-default px-3 py-2">
          <Text variant="secondary" className="text-[10px] font-medium">Layout:</Text>
          <button
            type="button"
            onClick={() => setLayout({ ...layout, type: "flex", direction: "row" })}
            className={`rounded-md p-1.5 transition ${layout.type === "flex" && layout.direction === "row" ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
          >
            <AlignHorizontalSpaceAround className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setLayout({ ...layout, type: "flex", direction: "column" })}
            className={`rounded-md p-1.5 transition ${layout.type === "flex" && layout.direction === "column" ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
          >
            <AlignVerticalSpaceAround className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setLayout({ ...layout, type: "grid", columns: 2 })}
            className={`rounded-md p-1.5 transition ${layout.type === "grid" ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
          >
            <Grid3X3 className="h-3.5 w-3.5" />
          </button>

          {layout.type === "grid" && (
            <div className="flex items-center gap-1 ml-2">
              <Text variant="secondary" className="text-[10px]">Cols:</Text>
              {[2, 3, 4].map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setLayout({ ...layout, columns: c })}
                  className={`rounded-xs px-1.5 py-0.5 text-[10px] font-medium ${layout.columns === c ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1 ml-2">
            <Text variant="secondary" className="text-[10px]">Gap:</Text>
            {[2, 4, 6, 8].map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setLayout({ ...layout, gap: g })}
                className={`rounded-xs px-1.5 py-0.5 text-[10px] font-medium ${layout.gap === g ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
              >
                {g}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={() => setShowCode(!showCode)}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition ${showCode ? "bg-action-primary text-text-inverse" : "bg-surface-muted text-text-secondary"}`}
            >
              <Code2 className="h-3 w-3" /> Code
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1 rounded-md bg-surface-muted px-2 py-1 text-[10px] font-medium text-text-secondary hover:text-text-primary transition"
            >
              {copied ? <Check className="h-3 w-3 text-state-success-text" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Export"}
            </button>
          </div>
        </div>

        {/* Canvas area */}
        <div className="flex-1 overflow-auto rounded-2xl border border-border-subtle">
          {showCode ? (
            <pre className="h-full overflow-auto bg-surface-inverse p-4 text-xs leading-relaxed text-border-subtle font-mono">
              {exportedCode}
            </pre>
          ) : (
            <PreviewThemeWrapper appearance="light" className="h-full min-h-[300px] p-6">
              {nodes.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <Grid3X3 className="mx-auto h-10 w-10 text-text-tertiary opacity-30" />
                    <Text variant="secondary" className="mt-2 text-sm">
                      Click a component from the palette to start building
                    </Text>
                  </div>
                </div>
              ) : (
                <div
                  className={
                    layout.type === "grid"
                      ? `grid gap-${layout.gap ?? 4}`
                      : `flex ${layout.direction === "column" ? "flex-col" : "flex-row"} gap-${layout.gap ?? 4}`
                  }
                  style={layout.type === "grid" ? { gridTemplateColumns: `repeat(${layout.columns ?? 2}, 1fr)` } : undefined}
                >
                  {nodes.map((node) => (
                    <div
                      key={node.id}
                      onClick={() => setSelectedId(node.id)}
                      className={`relative cursor-pointer rounded-lg p-2 transition ${
                        selectedId === node.id
                          ? "ring-2 ring-action-primary ring-offset-2"
                          : "hover:ring-1 hover:ring-border-subtle"
                      }`}
                    >
                      <PlaygroundPreview
                        componentName={node.componentName}
                        propValues={node.props as Record<string, string | number | boolean>}
                      />
                      {/* Node label */}
                      <div className="absolute -top-2 left-2 rounded-xs bg-surface-default px-1 py-0.5 text-[8px] font-mono font-bold text-text-tertiary shadow-xs border border-border-subtle">
                        {node.componentName}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </PreviewThemeWrapper>
          )}
        </div>
      </div>

      {/* Right: Props panel */}
      <div className="w-56 shrink-0 rounded-2xl border border-border-subtle bg-surface-default overflow-hidden flex flex-col">
        <div className="border-b border-border-subtle px-3 py-2">
          <Text as="div" className="text-xs font-semibold text-text-primary">
            {selectedNode ? `${selectedNode.componentName} Props` : "Properties"}
          </Text>
        </div>

        {selectedNode ? (
          <div className="flex flex-col flex-1 overflow-y-auto p-3 gap-2">
            {/* Reorder buttons */}
            <div className="flex items-center gap-1 mb-2">
              <button
                type="button"
                onClick={() => moveNode(selectedNode.id, "up")}
                className="rounded-xs p-1 text-text-tertiary hover:text-text-primary hover:bg-surface-muted transition text-[10px]"
              >
                Move Up
              </button>
              <button
                type="button"
                onClick={() => moveNode(selectedNode.id, "down")}
                className="rounded-xs p-1 text-text-tertiary hover:text-text-primary hover:bg-surface-muted transition text-[10px]"
              >
                Move Down
              </button>
              <button
                type="button"
                onClick={() => removeNode(selectedNode.id)}
                className="ml-auto rounded-xs p-1 text-state-danger-text hover:text-state-danger-text hover:bg-state-danger-bg transition"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Editable props */}
            <PropEditor label="children" value={selectedNode.props.children as string ?? ""} onChange={(v) => updateNodeProp(selectedNode.id, "children", v)} />
            <PropEditor label="variant" value={selectedNode.props.variant as string ?? ""} onChange={(v) => updateNodeProp(selectedNode.id, "variant", v)} />
            <PropEditor label="size" value={selectedNode.props.size as string ?? ""} onChange={(v) => updateNodeProp(selectedNode.id, "size", v)} />
            <PropEditor label="placeholder" value={selectedNode.props.placeholder as string ?? ""} onChange={(v) => updateNodeProp(selectedNode.id, "placeholder", v)} />
            <div className="flex items-center gap-2">
              <Text variant="secondary" className="text-[10px] w-16 shrink-0">disabled</Text>
              <input
                type="checkbox"
                checked={Boolean(selectedNode.props.disabled)}
                onChange={(e) => updateNodeProp(selectedNode.id, "disabled", e.target.checked)}
                className="rounded-xs"
              />
            </div>
            <div className="flex items-center gap-2">
              <Text variant="secondary" className="text-[10px] w-16 shrink-0">loading</Text>
              <input
                type="checkbox"
                checked={Boolean(selectedNode.props.loading)}
                onChange={(e) => updateNodeProp(selectedNode.id, "loading", e.target.checked)}
                className="rounded-xs"
              />
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-4">
            <Text variant="secondary" className="text-xs text-center">
              Select a component on the canvas to edit its properties
            </Text>
          </div>
        )}

        {/* Node list */}
        <div className="border-t border-border-subtle">
          <div className="px-3 py-1.5">
            <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-wider">
              Layers ({nodes.length})
            </Text>
          </div>
          <div className="flex flex-col max-h-36 overflow-y-auto px-2 pb-2 gap-0.5">
            {nodes.map((node, i) => (
              <button
                key={node.id}
                type="button"
                onClick={() => setSelectedId(node.id)}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[10px] transition ${
                  selectedId === node.id ? "bg-action-primary/10 text-action-primary" : "text-text-secondary hover:bg-surface-muted"
                }`}
              >
                <span className="font-mono">{i + 1}.</span>
                <span className="font-medium">{node.componentName}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Library modal */}
      {showLibrary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-surface-inverse/40" onClick={() => setShowLibrary(false)} />
          <div className="relative w-full max-w-md rounded-2xl border border-border-subtle bg-surface-default shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
              <Text as="h2" className="text-sm font-semibold text-text-primary">Saved Compositions</Text>
              <button type="button" onClick={() => setShowLibrary(false)} className="rounded-xs p-1 text-text-tertiary hover:text-text-primary">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex flex-col max-h-80 overflow-y-auto p-4 gap-2">
              {compositions.length === 0 ? (
                <Text variant="secondary" className="text-xs text-center py-8">No saved compositions yet</Text>
              ) : (
                compositions.map((comp) => (
                  <div key={comp.id} className="flex items-center justify-between rounded-xl border border-border-subtle p-3">
                    <div>
                      <Text className="text-xs font-medium text-text-primary">{comp.name}</Text>
                      <Text variant="secondary" className="text-[10px]">
                        {comp.nodes.length} components &middot; {new Date(comp.savedAt).toLocaleDateString()}
                      </Text>
                    </div>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => handleLoad(comp)}
                        className="rounded-md bg-action-primary/10 px-2 py-1 text-[10px] font-medium text-action-primary hover:bg-action-primary/20 transition"
                      >
                        Load
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteComposition(comp.id)}
                        className="rounded-md p-1 text-text-tertiary hover:text-state-danger-text transition"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Prop Editor row ---- */

function PropEditor({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <Text variant="secondary" className="text-[10px] w-16 shrink-0">{label}</Text>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded-md border border-border-subtle bg-surface-canvas px-2 py-1 text-[11px] outline-hidden focus:border-action-primary"
        placeholder={label}
      />
    </div>
  );
}
