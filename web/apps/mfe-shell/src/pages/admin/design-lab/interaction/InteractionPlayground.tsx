import React, { useState, _useMemo, useCallback, useRef, useEffect } from "react";
import {
  Zap,
  Play as _Play,
  RotateCcw,
  ChevronRight as _ChevronRight,
  ArrowRight,
  Unplug as _Unplug,
  Cable,
} from "lucide-react";
import { Text } from "@mfe/design-system";
import { PlaygroundPreview } from "../playground/PlaygroundPreview";
import { PreviewThemeWrapper } from "../playground/PreviewThemeWrapper";
import { SCENARIOS } from "./interactionScenarios";
import type { InteractionScenario } from "./interactionScenarios";

/* ------------------------------------------------------------------ */
/*  InteractionPlayground — Cross-component interaction demo           */
/*                                                                     */
/*  Features:                                                          */
/*  - Pre-built interaction scenarios                                  */
/*  - Visual wiring between components (SVG lines)                     */
/*  - Shared reactive state between components                         */
/*  - Real-time interaction preview                                    */
/*                                                                     */
/*  Unique: No competitor has cross-component interaction playground.   */
/* ------------------------------------------------------------------ */

type NodeState = Record<string, unknown>; // nodeId → current value

export default function InteractionPlayground() {
  const [selectedScenario, setSelectedScenario] = useState<InteractionScenario>(SCENARIOS[0]);
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({});
  const [activeWire, setActiveWire] = useState<string | null>(null);
  const [eventLog, setEventLog] = useState<Array<{ time: string; from: string; to: string; value: string }>>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize node states when scenario changes
  useEffect(() => {
    const states: Record<string, NodeState> = {};
    selectedScenario.nodes.forEach((node) => {
      states[node.id] = { ...node.props };
    });
    setNodeStates(states);
    setEventLog([]);
  }, [selectedScenario]);

  // Process an event from a source node
  const handleNodeEvent = useCallback(
    (sourceNodeId: string, eventName: string, value: unknown) => {
      const relevantWires = selectedScenario.wires.filter(
        (w) => w.from.nodeId === sourceNodeId && w.from.event === eventName,
      );

      if (relevantWires.length === 0) return;

      setNodeStates((prev) => {
        const next = { ...prev };
        relevantWires.forEach((wire) => {
          const targetNode = next[wire.to.nodeId];
          if (!targetNode) return;

          let transformedValue = value;
          if (wire.transform === "!value") {
            transformedValue = !value;
          } else if (wire.transform === "value") {
            transformedValue = value;
          }

          next[wire.to.nodeId] = { ...targetNode, [wire.to.prop]: transformedValue };

          // Highlight wire
          setActiveWire(wire.id);
          setTimeout(() => setActiveWire(null), 500);
        });
        return next;
      });

      // Add to event log
      relevantWires.forEach((wire) => {
        setEventLog((prev) => [
          {
            time: new Date().toLocaleTimeString(),
            from: `${sourceNodeId}.${eventName}`,
            to: `${wire.to.nodeId}.${wire.to.prop}`,
            value: String(value),
          },
          ...prev.slice(0, 19),
        ]);
      });
    },
    [selectedScenario],
  );

  const resetScenario = useCallback(() => {
    const states: Record<string, NodeState> = {};
    selectedScenario.nodes.forEach((node) => {
      states[node.id] = { ...node.props };
    });
    setNodeStates(states);
    setEventLog([]);
  }, [selectedScenario]);

  return (
    <div className="flex flex-col mx-auto max-w-6xl gap-4 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-state-warning-text/20 to-state-danger-text/20">
          <Zap className="h-5 w-5 text-state-warning-text" />
        </div>
        <div>
          <Text as="h1" className="text-xl font-bold text-text-primary">Interaction Playground</Text>
          <Text variant="secondary" className="text-sm">
            Cross-component interactions with shared state
          </Text>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Scenario selector */}
        <div className="flex flex-col w-64 shrink-0 gap-2">
          <Text as="div" className="text-xs font-semibold text-text-primary mb-2">Scenarios</Text>
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              onClick={() => setSelectedScenario(scenario)}
              className={[
                "w-full rounded-xl border p-3 text-left transition",
                selectedScenario.id === scenario.id
                  ? "border-action-primary bg-action-primary/5"
                  : "border-border-subtle hover:border-action-primary/30",
              ].join(" ")}
            >
              <Text className="text-xs font-semibold text-text-primary">{scenario.name}</Text>
              <Text variant="secondary" className="text-[10px] mt-0.5">{scenario.description}</Text>
              <div className="mt-1.5 flex items-center gap-1">
                <span className="rounded-xs bg-surface-muted px-1.5 py-0.5 text-[9px] font-medium text-text-tertiary">
                  {scenario.nodes.length} nodes
                </span>
                <span className="rounded-xs bg-surface-muted px-1.5 py-0.5 text-[9px] font-medium text-text-tertiary">
                  {scenario.wires.length} wires
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Main area */}
        <div className="flex flex-col flex-1 gap-3">
          {/* Toolbar */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={resetScenario}
              className="flex items-center gap-1.5 rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </button>
            <div className="ml-auto flex items-center gap-1.5 text-[10px] text-text-tertiary">
              <Cable className="h-3.5 w-3.5" />
              {selectedScenario.wires.length} connections
            </div>
          </div>

          {/* Interactive canvas */}
          <div ref={containerRef} className="relative rounded-2xl border border-border-subtle overflow-hidden">
            <PreviewThemeWrapper appearance="light" className="min-h-[350px] p-6">
              {/* Wiring visualization (SVG overlay) */}
              <svg className="pointer-events-none absolute inset-0 h-full w-full" style={{ zIndex: 10 }}>
                {selectedScenario.wires.map((wire) => {
                  const fromNode = selectedScenario.nodes.find((n) => n.id === wire.from.nodeId);
                  const toNode = selectedScenario.nodes.find((n) => n.id === wire.to.nodeId);
                  if (!fromNode || !toNode) return null;
                  const isActive = activeWire === wire.id;

                  // Simple connection lines based on node positions
                  const x1 = fromNode.x + 150;
                  const y1 = fromNode.y + 20;
                  const x2 = toNode.x + 10;
                  const y2 = toNode.y + 20;

                  // Only draw if nodes are on different x positions
                  if (Math.abs(fromNode.x - toNode.x) < 50) return null;

                  return (
                    <g key={wire.id}>
                      <line
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke={isActive ? "var(--state-warning-text)" : "var(--text-subtle)"}
                        strokeWidth={isActive ? 2.5 : 1.5}
                        strokeDasharray={isActive ? "none" : "4 4"}
                        className="transition-all duration-300"
                      />
                      {/* Arrow */}
                      <circle
                        cx={x2}
                        cy={y2}
                        r={3}
                        fill={isActive ? "var(--state-warning-text)" : "var(--text-subtle)"}
                      />
                    </g>
                  );
                })}
              </svg>

              {/* Nodes */}
              <div className="flex flex-col gap-4">
                {selectedScenario.nodes.map((node) => {
                  const currentProps = nodeStates[node.id] ?? node.props;
                  const isHidden = currentProps.visible === false;

                  return (
                    <div key={node.id} className="relative">
                      {/* Node label */}
                      <div className="mb-1 flex items-center gap-1.5">
                        <code className="text-[10px] font-mono font-bold text-text-tertiary">
                          {node.id}
                        </code>
                        <span className="rounded-xs bg-surface-muted px-1 py-0.5 text-[9px] font-medium text-text-secondary">
                          {node.componentName}
                        </span>
                        {/* Show connected events */}
                        {selectedScenario.wires
                          .filter((w) => w.from.nodeId === node.id)
                          .map((w) => (
                            <span key={w.id} className="flex items-center gap-0.5 text-[9px] text-state-warning-text">
                              <ArrowRight className="h-2.5 w-2.5" />
                              {w.to.nodeId}.{w.to.prop}
                            </span>
                          ))}
                      </div>

                      {/* Component */}
                      {!isHidden && (
                        <div
                          className="inline-block"
                          onClick={() => {
                            // Simulate toggle for checkbox/switch
                            if (node.componentName === "Checkbox" || node.componentName === "Switch") {
                              const current = Boolean(currentProps.checked);
                              setNodeStates((prev) => ({
                                ...prev,
                                [node.id]: { ...prev[node.id], checked: !current },
                              }));
                              handleNodeEvent(node.id, "onChange", !current);
                            }
                          }}
                          onInput={(e) => {
                            // Simulate input change
                            if (node.componentName === "Input") {
                              const val = (e.target as HTMLInputElement).value;
                              setNodeStates((prev) => ({
                                ...prev,
                                [node.id]: { ...prev[node.id], value: val },
                              }));
                              handleNodeEvent(node.id, "onChange", val);
                            }
                          }}
                          onChange={(e) => {
                            // Simulate select change
                            if (node.componentName === "Select") {
                              const val = (e.target as HTMLSelectElement).value;
                              setNodeStates((prev) => ({
                                ...prev,
                                [node.id]: { ...prev[node.id], value: val },
                              }));
                              handleNodeEvent(node.id, "onChange", val);
                            }
                          }}
                        >
                          <PlaygroundPreview
                            componentName={node.componentName}
                            propValues={currentProps as Record<string, string | number | boolean>}
                          />
                        </div>
                      )}
                      {isHidden && (
                        <div className="rounded-lg border border-dashed border-border-subtle px-4 py-2 text-[10px] text-text-tertiary">
                          {node.componentName} (hidden)
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </PreviewThemeWrapper>
          </div>

          {/* Event log */}
          <div className="rounded-2xl border border-border-subtle overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border-subtle bg-surface-canvas px-4 py-2">
              <Zap className="h-3.5 w-3.5 text-state-warning-text" />
              <Text as="span" className="text-xs font-semibold text-text-primary">Event Log</Text>
              <span className="ml-auto text-[10px] text-text-tertiary">{eventLog.length} events</span>
            </div>
            <div className="max-h-40 overflow-y-auto">
              {eventLog.length === 0 ? (
                <div className="px-4 py-6 text-center">
                  <Text variant="secondary" className="text-xs">
                    Interact with components above to see events flow
                  </Text>
                </div>
              ) : (
                <div className="divide-y divide-border-subtle">
                  {eventLog.map((entry, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-1.5 text-[10px]">
                      <span className="font-mono text-text-tertiary">{entry.time}</span>
                      <code className="font-mono font-medium text-action-primary">{entry.from}</code>
                      <ArrowRight className="h-3 w-3 text-state-warning-text" />
                      <code className="font-mono font-medium text-state-success-text">{entry.to}</code>
                      <span className="ml-auto truncate font-mono text-text-secondary max-w-[120px]">
                        = {entry.value}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Wiring diagram legend */}
          <div className="flex items-center gap-4 rounded-xl border border-border-subtle bg-surface-canvas px-4 py-2">
            <Text variant="secondary" className="text-[10px] font-medium">Legend:</Text>
            <div className="flex items-center gap-1.5">
              <div className="h-0.5 w-6 bg-state-warning-text rounded-xs" />
              <Text variant="secondary" className="text-[10px]">Active wire</Text>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-0.5 w-6 rounded-xs bg-[var(--text-subtle)]" style={{ backgroundImage: "repeating-linear-gradient(90deg, var(--text-subtle)) 0 4px, transparent 4px 8px)" }} />
              <Text variant="secondary" className="text-[10px]">Idle wire</Text>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-state-warning-text" />
              <Text variant="secondary" className="text-[10px]">Target node</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
