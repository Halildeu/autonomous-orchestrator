#!/usr/bin/env node
/**
 * build-tokens.mjs
 * ----------------
 * Faz 4A  Token build pipeline.
 *
 * Reads design-system token .ts source files, parses the exported const
 * objects, and emits three artifacts into packages/design-system/src/tokens/build/:
 *
 *   1. tokens.json       Unified JSON with every token organised by category.
 *   2. tokens.css         CSS custom properties (:root block).
 *   3. token-types.ts     TypeScript union types for each token category.
 *
 * Usage:  node scripts/tokens/build-tokens.mjs [--check]
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

/* ------------------------------------------------------------------ */
/*  Paths                                                              */
/* ------------------------------------------------------------------ */
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = join(__dirname, "../..");
const TOKENS_SRC = join(ROOT, "packages/design-system/src/tokens");
const BUILD_DIR = join(TOKENS_SRC, "build");
const args = new Set(process.argv.slice(2));
const isCheckMode = args.has("--check");

if (!isCheckMode) {
  mkdirSync(BUILD_DIR, { recursive: true });
}

/* ------------------------------------------------------------------ */
/*  Token source files to process (order matters for output)           */
/* ------------------------------------------------------------------ */
const TOKEN_FILES = [
  "color.ts",
  "spacing.ts",
  "radius.ts",
  "typography.ts",
  "motion.ts",
  "zIndex.ts",
  "elevation.ts",
  "opacity.ts",
  "density.ts",
  "focusRing.ts",
  "semantic.ts",
];

/* ------------------------------------------------------------------ */
/*  Parser — extract `export const X = { ... } as const` blocks        */
/* ------------------------------------------------------------------ */

/**
 * Parse a single value literal from TypeScript source.
 * Handles strings, numbers, and nested objects.
 */
function parseValue(raw) {
  const trimmed = raw.trim();

  // String value (single or double quotes, or backticks)
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.startsWith("`") && trimmed.endsWith("`"))
  ) {
    return trimmed.slice(1, -1);
  }

  // Number
  if (!Number.isNaN(Number(trimmed)) && trimmed !== "") {
    return Number(trimmed);
  }

  return trimmed; // fallback — keep as string
}

/**
 * Extract the balanced brace content starting from `startIdx` in `src`.
 * `startIdx` must point at the opening `{`.
 */
function extractBraceBlock(src, startIdx) {
  let depth = 0;
  let i = startIdx;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(startIdx, i + 1);
    }
  }
  return src.slice(startIdx);
}

/**
 * Parse a flat or one-level-nested object literal string into a JS object.
 * Strips comments, handles quoted keys and numeric keys.
 */
function parseObjectLiteral(block) {
  // Remove outer braces
  let inner = block.trim();
  if (inner.startsWith("{")) inner = inner.slice(1);
  if (inner.endsWith("}")) inner = inner.slice(0, -1);

  // Strip single-line comments
  inner = inner.replace(/\/\/.*$/gm, "");
  // Strip block comments
  inner = inner.replace(/\/\*[\s\S]*?\*\//g, "");

  const result = {};

  // Tokenise key-value pairs. We walk character-by-character to handle
  // nested objects and string values that may contain commas.
  let i = 0;
  while (i < inner.length) {
    // Skip whitespace / commas
    while (i < inner.length && /[\s,]/.test(inner[i])) i++;
    if (i >= inner.length) break;

    // ---- Parse key ----
    let key = "";
    if (inner[i] === '"' || inner[i] === "'") {
      const q = inner[i];
      i++; // skip opening quote
      while (i < inner.length && inner[i] !== q) {
        key += inner[i];
        i++;
      }
      i++; // skip closing quote
    } else {
      while (i < inner.length && inner[i] !== ":" && !/[\s]/.test(inner[i])) {
        key += inner[i];
        i++;
      }
    }
    key = key.trim();
    if (!key) break;

    // Skip to colon
    while (i < inner.length && inner[i] !== ":") i++;
    i++; // skip colon

    // Skip whitespace
    while (i < inner.length && /\s/.test(inner[i])) i++;

    // ---- Parse value ----
    if (inner[i] === "{") {
      // Nested object
      const nested = extractBraceBlock(inner, i);
      result[key] = parseObjectLiteral(nested);
      i += nested.length;
    } else if (inner[i] === '"' || inner[i] === "'" || inner[i] === "`") {
      const q = inner[i];
      i++; // skip opening quote
      let val = "";
      while (i < inner.length && inner[i] !== q) {
        if (inner[i] === "\\" && i + 1 < inner.length) {
          val += inner[i + 1];
          i += 2;
        } else {
          val += inner[i];
          i++;
        }
      }
      i++; // skip closing quote
      result[key] = val;
    } else {
      // Number or identifier
      let val = "";
      while (
        i < inner.length &&
        inner[i] !== "," &&
        inner[i] !== "}" &&
        inner[i] !== "\n"
      ) {
        val += inner[i];
        i++;
      }
      result[key] = parseValue(val);
    }
  }
  return result;
}

/**
 * Given a .ts file's source, return an array of { name, value } for every
 * `export const <name> = { ... } as const` declaration found.
 */
function extractExportedConsts(source) {
  const results = [];
  // Match `export const NAME = {`  (the opening brace must be on this line or next)
  const pattern = /export\s+const\s+(\w+)\s*=\s*\{/g;
  let m;
  while ((m = pattern.exec(source)) !== null) {
    const name = m[1];
    const braceStart = m.index + m[0].length - 1; // point at `{`
    const block = extractBraceBlock(source, braceStart);
    results.push({ name, value: parseObjectLiteral(block) });
  }
  return results;
}

/* ------------------------------------------------------------------ */
/*  Read & parse every token file                                      */
/* ------------------------------------------------------------------ */
const allTokens = {};
const exportNames = []; // [{ category, name, keys }]

for (const file of TOKEN_FILES) {
  const filePath = join(TOKENS_SRC, file);
  let source;
  try {
    source = readFileSync(filePath, "utf-8");
  } catch {
    console.warn(`  [skip] ${file} not found`);
    continue;
  }

  const consts = extractExportedConsts(source);
  if (consts.length === 0) {
    // File may only contain interfaces (e.g. semantic.ts)
    continue;
  }

  const category = file.replace(/\.ts$/, "");
  for (const { name, value } of consts) {
    // Merge into allTokens under category or directly by export name
    if (!allTokens[category]) allTokens[category] = {};
    allTokens[category][name] = value;
    exportNames.push({
      category,
      name,
      keys: Object.keys(value),
      value,
    });
  }
}

/* ------------------------------------------------------------------ */
/*  1. tokens.json                                                     */
/* ------------------------------------------------------------------ */
const jsonPath = join(BUILD_DIR, "tokens.json");
const jsonContent = JSON.stringify(allTokens, null, 2) + "\n";

/* ------------------------------------------------------------------ */
/*  2. tokens.css                                                      */
/* ------------------------------------------------------------------ */

/**
 * Convert a camelCase or PascalCase key to kebab-case.
 */
function toKebab(str) {
  return str
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1-$2")
    .toLowerCase();
}

/**
 * Flatten a (possibly nested) token object into CSS custom property
 * declarations.  Prefix is built up as we recurse.
 */
function flattenToCSS(obj, prefix) {
  const lines = [];
  for (const [key, val] of Object.entries(obj)) {
    const prop = `--${prefix}-${toKebab(String(key))}`;
    if (typeof val === "object" && val !== null && !Array.isArray(val)) {
      lines.push(...flattenToCSS(val, `${prefix}-${toKebab(String(key))}`));
    } else {
      /* Wrap bare CSS variable references (e.g. "--surface-default") in var() */
      const cssVal = typeof val === "string" && /^--[\w-]+$/.test(val) ? `var(${val})` : val;
      lines.push(`  ${prop}: ${cssVal};`);
    }
  }
  return lines;
}

let cssContent =
  `/* ------------------------------------------------------------------ */\n` +
  `/*  AUTO-GENERATED by build-tokens.mjs — do not edit                  */\n` +
  `/* ------------------------------------------------------------------ */\n\n` +
  `:root {\n`;

for (const { category, name, value } of exportNames) {
  const prefix = toKebab(name);
  cssContent += `\n  /* --- ${category} / ${name} --- */\n`;
  cssContent += flattenToCSS(value, prefix).join("\n") + "\n";
}

cssContent += `}\n`;

const cssPath = join(BUILD_DIR, "tokens.css");

/* ------------------------------------------------------------------ */
/*  3. token-types.ts                                                  */
/* ------------------------------------------------------------------ */

let tsContent =
  `/* ------------------------------------------------------------------ */\n` +
  `/*  AUTO-GENERATED by build-tokens.mjs — do not edit                  */\n` +
  `/* ------------------------------------------------------------------ */\n\n`;

for (const { name, keys } of exportNames) {
  const typeName = name.charAt(0).toUpperCase() + name.slice(1) + "Token";
  const union = keys.map((k) => `  | ${JSON.stringify(String(k))}`).join("\n");
  tsContent += `export type ${typeName} =\n${union};\n\n`;
}

const tsPath = join(BUILD_DIR, "token-types.ts");

/* ------------------------------------------------------------------ */
/*  4. docs.json                                                       */
/* ------------------------------------------------------------------ */

/**
 * Build a docs-friendly array of token entries for Design Lab's token viewer.
 * Each entry includes: name, category, value, cssVariable, description.
 */
function buildDocsEntries(exportEntries) {
  const docs = [];

  for (const { category, name, value } of exportEntries) {
    const prefix = toKebab(name);

    function walk(obj, pathParts, cssPrefix) {
      for (const [key, val] of Object.entries(obj)) {
        const tokenPath = [...pathParts, key];
        const cssProp = `--${cssPrefix}-${toKebab(String(key))}`;

        if (typeof val === "object" && val !== null && !Array.isArray(val)) {
          walk(val, tokenPath, `${cssPrefix}-${toKebab(String(key))}`);
        } else {
          docs.push({
            name: tokenPath.join("."),
            category,
            value: val,
            cssVariable: cssProp,
            description: "",
          });
        }
      }
    }

    walk(value, [name], prefix);
  }

  return docs;
}

const docsEntries = buildDocsEntries(exportNames);
const docsPath = join(BUILD_DIR, "docs.json");
const docsContent = JSON.stringify(docsEntries, null, 2) + "\n";

const outputs = [
  ["tokens.json", jsonPath, jsonContent],
  ["tokens.css", cssPath, cssContent],
  ["token-types.ts", tsPath, tsContent],
  ["docs.json", docsPath, docsContent],
];

if (isCheckMode) {
  const errors = [];
  for (const [label, outputPath, content] of outputs) {
    try {
      const existing = readFileSync(outputPath, "utf-8");
      if (existing !== content) {
        errors.push(`- Drift: ${relative(ROOT, outputPath)} generated output is not up to date (${label}).`);
      }
    } catch {
      errors.push(`- Missing: ${relative(ROOT, outputPath)} does not exist (${label}).`);
    }
  }

  if (errors.length > 0) {
    console.error("❌ tokens:build drift detected (run: pnpm -C web run tokens:build)");
    errors.forEach((line) => console.error(line));
    process.exit(1);
  }

  console.log(`✅ tokens:build --check OK (${outputs.length} files)`);
} else {
  mkdirSync(BUILD_DIR, { recursive: true });
  for (const [, outputPath, content] of outputs) {
    writeFileSync(outputPath, content, "utf-8");
    console.log(`  [ok] ${outputPath}`);
  }
}

/* ------------------------------------------------------------------ */
/*  Summary                                                            */
/* ------------------------------------------------------------------ */
const totalTokens = exportNames.reduce((s, e) => s + e.keys.length, 0);
console.log(
  `\n  Build complete — ${exportNames.length} exports, ${totalTokens} top-level keys.`
);
