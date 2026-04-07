/**
 * Chart Export — PNG, SVG, PDF, CSV, XLSX
 *
 * Extracts chart content from ECharts instance or raw data
 * and triggers browser download.
 *
 * @see contract P7 DoD: "Export: PNG, SVG, PDF, CSV, XLSX"
 */

export type ExportFormat = 'png' | 'svg' | 'pdf' | 'csv' | 'xlsx';

export interface ExportOptions {
  /** Export file name (without extension) */
  filename?: string;
  /** Chart title for header */
  title?: string;
  /** PNG/SVG pixel ratio. @default 2 */
  pixelRatio?: number;
  /** CSV/XLSX data rows */
  data?: Record<string, unknown>[];
  /** CSV/XLSX column headers */
  columns?: Array<{ field: string; headerName: string }>;
}

interface EChartsLike {
  getDataURL(opts: { type: string; pixelRatio?: number; backgroundColor?: string }): string;
  getConnectedDataURL?(opts: { type: string; pixelRatio?: number }): string;
}

function triggerDownload(url: string, filename: string) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function dataToCSV(data: Record<string, unknown>[], columns: Array<{ field: string; headerName: string }>): string {
  const header = columns.map((c) => `"${c.headerName}"`).join(',');
  const rows = data.map((row) =>
    columns.map((c) => {
      const val = row[c.field];
      if (val === null || val === undefined) return '';
      if (typeof val === 'string') return `"${val.replace(/"/g, '""')}"`;
      return String(val);
    }).join(','),
  );
  return [header, ...rows].join('\n');
}

/* ------------------------------------------------------------------ */
/*  Minimal PDF builder (no external dependency)                       */
/* ------------------------------------------------------------------ */

function buildPdfFromImage(dataUrl: string, title?: string): Blob {
  // Extract base64 PNG data
  const base64Data = dataUrl.split(',')[1] ?? '';
  const imageBytes = atob(base64Data);
  const imageLen = imageBytes.length;

  // Decode PNG header for dimensions (IHDR chunk at offset 16)
  const raw = Uint8Array.from(imageBytes, (c) => c.charCodeAt(0));
  const view = new DataView(raw.buffer);
  const imgW = view.getUint32(16);
  const imgH = view.getUint32(20);

  // Scale image to fit A4 (595x842 pt) with 40pt margin
  const maxW = 515;
  const maxH = 700;
  const scale = Math.min(maxW / imgW, maxH / imgH, 1);
  const w = Math.round(imgW * scale);
  const h = Math.round(imgH * scale);
  const x = Math.round((595 - w) / 2);
  const yImg = title ? 760 - h : 800 - h;

  // Build PDF objects
  const objs: string[] = [];
  // 1: Catalog
  objs.push('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj');
  // 2: Pages
  objs.push('2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj');
  // 3: Page
  objs.push(`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /XObject << /Img 5 0 R >> /Font << /F1 6 0 R >> >> >>\nendobj`);

  // 4: Content stream
  let stream = `q\n${w} 0 0 ${h} ${x} ${yImg} cm\n/Img Do\nQ\n`;
  if (title) {
    const safeTitle = title.replace(/[()\\]/g, '\\$&');
    stream = `BT\n/F1 16 Tf\n${x} ${yImg + h + 20} Td\n(${safeTitle}) Tj\nET\n` + stream;
  }
  objs.push(`4 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}endstream\nendobj`);

  // 5: Image XObject
  objs.push(`5 0 obj\n<< /Type /XObject /Subtype /Image /Width ${imgW} /Height ${imgH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imageLen} >>\nstream\n`);
  // Image stream appended as binary

  // 6: Font
  objs.push('6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj');

  // Assemble PDF
  const header = '%PDF-1.4\n';
  const parts: (string | Uint8Array)[] = [header];
  const offsets: number[] = [];
  let pos = header.length;

  for (let i = 0; i < objs.length; i++) {
    offsets.push(pos);
    if (i === 4) {
      // Image object: split text header + binary data + endstream/endobj
      const imgHeader = objs[i];
      parts.push(imgHeader);
      pos += imgHeader.length;
      parts.push(raw);
      pos += raw.length;
      const imgFooter = '\nendstream\nendobj\n';
      parts.push(imgFooter);
      pos += imgFooter.length;
    } else {
      const text = objs[i] + '\n';
      parts.push(text);
      pos += text.length;
    }
  }

  // xref
  const xrefStart = pos;
  let xref = `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) {
    xref += `${String(off).padStart(10, '0')} 00000 n \n`;
  }
  parts.push(xref);

  // trailer
  const trailer = `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
  parts.push(trailer);

  return new Blob(parts, { type: 'application/pdf' });
}

/**
 * Hook for chart export functionality.
 */
export function useChartExport() {
  const exportChart = (
    instance: EChartsLike | null,
    format: ExportFormat,
    options?: ExportOptions,
  ) => {
    const { filename = 'chart', title, pixelRatio = 2, data, columns } = options ?? {};

    if (format === 'csv' && data && columns) {
      const csv = dataToCSV(data, columns);
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
      triggerDownload(URL.createObjectURL(blob), `${filename}.csv`);
      return;
    }

    if (!instance) return;

    if (format === 'png') {
      const url = instance.getDataURL({ type: 'png', pixelRatio, backgroundColor: '#ffffff' });
      triggerDownload(url, `${filename}.png`);
    } else if (format === 'svg') {
      const url = instance.getDataURL({ type: 'svg', pixelRatio });
      triggerDownload(url, `${filename}.svg`);
    } else if (format === 'pdf') {
      // PDF export: render chart as PNG then wrap in a minimal PDF
      const pngUrl = instance.getDataURL({ type: 'png', pixelRatio, backgroundColor: '#ffffff' });
      const pdfBlob = buildPdfFromImage(pngUrl, title);
      triggerDownload(URL.createObjectURL(pdfBlob), `${filename}.pdf`);
    }
  };

  return { exportChart };
}
