/**
 * Smart Chart Type Suggestion
 *
 * Analyzes data shape (column types, cardinality, value ranges)
 * to suggest the most appropriate chart type. No LLM needed —
 * rule-based heuristics.
 *
 * @see contract P5 DoD: "Smart chart type suggestion based on data shape"
 * @see mfe-reporting/src/visualization/chartTypeInference.ts (similar, simpler)
 */

import type { ChartType } from '../spec/ChartSpec';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DataShapeAnalysis {
  rowCount: number;
  columns: Array<{
    field: string;
    type: 'string' | 'number' | 'date' | 'boolean';
    cardinality: number;
    hasNulls: boolean;
  }>;
  stringColumns: number;
  numberColumns: number;
  dateColumns: number;
}

export interface ChartTypeSuggestion {
  type: ChartType;
  confidence: number; // 0-1
  reason: string;
}

/* ------------------------------------------------------------------ */
/*  Data Shape Analyzer                                                */
/* ------------------------------------------------------------------ */

function analyzeShape(data: Record<string, unknown>[]): DataShapeAnalysis {
  if (data.length === 0) {
    return { rowCount: 0, columns: [], stringColumns: 0, numberColumns: 0, dateColumns: 0 };
  }

  const sample = data.slice(0, Math.min(100, data.length));
  const fields = Object.keys(sample[0]);

  const columns = fields.map((field) => {
    const values = sample.map((r) => r[field]);
    const nonNull = values.filter((v) => v != null);
    const unique = new Set(nonNull.map(String));

    let type: 'string' | 'number' | 'date' | 'boolean' = 'string';
    if (nonNull.length > 0) {
      if (typeof nonNull[0] === 'number') type = 'number';
      else if (typeof nonNull[0] === 'boolean') type = 'boolean';
      else if (nonNull[0] instanceof Date || (typeof nonNull[0] === 'string' && !isNaN(Date.parse(nonNull[0] as string)) && (nonNull[0] as string).length > 7)) type = 'date';
    }

    return {
      field,
      type,
      cardinality: unique.size,
      hasNulls: nonNull.length < values.length,
    };
  });

  return {
    rowCount: data.length,
    columns,
    stringColumns: columns.filter((c) => c.type === 'string').length,
    numberColumns: columns.filter((c) => c.type === 'number').length,
    dateColumns: columns.filter((c) => c.type === 'date').length,
  };
}

/* ------------------------------------------------------------------ */
/*  Suggestion Engine                                                  */
/* ------------------------------------------------------------------ */

/**
 * Suggest up to 5 chart types ranked by confidence.
 *
 * Rules:
 *   - date + number → line (time series)
 *   - 1 string (low card) + 1 number → bar
 *   - 1 string (low card) + 1 number (proportion) → pie
 *   - 2 numbers → scatter
 *   - 1 string (high card) + 1 number → horizontal bar
 *   - multiple numbers → radar
 *   - hierarchical (name+parent+value) → treemap
 *   - 2 strings + 1 number → heatmap
 */
export function suggestChartType(
  data: Record<string, unknown>[],
  maxSuggestions = 5,
): ChartTypeSuggestion[] {
  const shape = analyzeShape(data);
  const suggestions: ChartTypeSuggestion[] = [];

  if (shape.rowCount === 0) return [{ type: 'bar', confidence: 0.5, reason: 'Varsayılan (veri yok)' }];

  const strings = shape.columns.filter((c) => c.type === 'string');
  const numbers = shape.columns.filter((c) => c.type === 'number');
  const dates = shape.columns.filter((c) => c.type === 'date');

  // Time series
  if (dates.length >= 1 && numbers.length >= 1) {
    suggestions.push({ type: 'line', confidence: 0.9, reason: 'Tarih + sayısal veri → zaman serisi' });
    suggestions.push({ type: 'area', confidence: 0.75, reason: 'Tarih + sayısal → alan grafiği alternatif' });
  }

  // Category + value
  if (strings.length >= 1 && numbers.length >= 1) {
    const catCard = strings[0].cardinality;

    if (catCard <= 8) {
      suggestions.push({ type: 'bar', confidence: 0.85, reason: `Düşük kardinalite (${catCard}) kategorik → çubuk` });
      suggestions.push({ type: 'pie', confidence: 0.6, reason: `${catCard} kategori → pasta (oran gösterimi)` });
    } else if (catCard <= 20) {
      suggestions.push({ type: 'bar', confidence: 0.8, reason: `Orta kardinalite (${catCard}) → yatay çubuk` });
    } else {
      suggestions.push({ type: 'bar', confidence: 0.5, reason: `Yüksek kardinalite (${catCard}) → çubuk (filtre önerilir)` });
    }
  }

  // Two numbers → scatter
  if (numbers.length >= 2) {
    suggestions.push({ type: 'scatter', confidence: 0.7, reason: '2+ sayısal kolon → dağılım' });
  }

  // Multiple numbers → radar
  if (numbers.length >= 3 && shape.rowCount <= 10) {
    suggestions.push({ type: 'radar', confidence: 0.65, reason: '3+ metrik, az satır → radar profili' });
  }

  // Two strings + number → heatmap
  if (strings.length >= 2 && numbers.length >= 1) {
    suggestions.push({ type: 'heatmap', confidence: 0.55, reason: '2 kategorik + 1 sayısal → ısı haritası' });
  }

  // Single number → gauge
  if (shape.rowCount === 1 && numbers.length >= 1) {
    suggestions.push({ type: 'gauge', confidence: 0.8, reason: 'Tek değer → gösterge' });
  }

  // Hierarchical data → treemap / sunburst
  const hasNameField = shape.columns.some((c) => c.type === 'string' && ['name', 'label', 'category'].includes(c.field.toLowerCase()));
  const hasParentField = shape.columns.some((c) => c.type === 'string' && ['parent', 'parent_id', 'parentId', 'group'].includes(c.field.toLowerCase()));
  const hasChildrenField = data.some((r) => Array.isArray(r.children));
  const hasValueField = numbers.length >= 1;

  if ((hasNameField && hasParentField && hasValueField) || hasChildrenField) {
    suggestions.push({ type: 'treemap', confidence: 0.8, reason: 'Hiyerarşik yapı (name+parent/children+value) → ağaç haritası' });
    suggestions.push({ type: 'sunburst', confidence: 0.7, reason: 'Hiyerarşik yapı → güneş patlaması alternatif' });
  }

  // Sort by confidence, take top N
  suggestions.sort((a, b) => b.confidence - a.confidence);
  return suggestions.slice(0, maxSuggestions);
}
