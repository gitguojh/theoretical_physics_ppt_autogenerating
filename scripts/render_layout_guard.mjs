#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const DEFAULT_IGNORE_ROLE_PATTERN = /footer|page number|citation|cover|label text/i;

export function normalizeText(text) {
  return Array.isArray(text) ? text.join("\n") : String(text ?? "");
}

export function textLineCount(text) {
  const value = normalizeText(text);
  return value.trim() ? value.split(/\n/).length : 0;
}

export function estimateCharWidth(char, fontSize) {
  if (/\s/.test(char)) return fontSize * 0.22;
  if (/[A-Z]/.test(char)) return fontSize * 0.5;
  if (/[a-z]/.test(char)) return fontSize * 0.4;
  if (/[0-9]/.test(char)) return fontSize * 0.42;
  if (/[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/.test(char)) return fontSize * 0.95;
  if (/[~_=+\-]/.test(char)) return fontSize * 0.34;
  if (/[.,;:!?'"()[\]{}]/.test(char)) return fontSize * 0.18;
  return fontSize * 0.38;
}

export function estimateWrappedLineCount(text, boxWidth, fontSize) {
  const value = normalizeText(text).trim();
  if (!value) return 0;
  const paragraphs = value.split(/\n/);
  const safeWidth = Math.max(24, Number(boxWidth) || 0);
  let totalLines = 0;
  for (const paragraph of paragraphs) {
    let lineWidth = 0;
    let lineCount = 1;
    for (const char of paragraph) {
      const charWidth = estimateCharWidth(char, fontSize);
      if (lineWidth + charWidth > safeWidth) {
        lineCount += 1;
        lineWidth = charWidth;
      } else {
        lineWidth += charWidth;
      }
    }
    totalLines += lineCount;
  }
  return totalLines;
}

export function requiredTextHeight(text, boxWidth, fontSize, lineHeight = 1.18, minHeight = 8) {
  const lines = estimateWrappedLineCount(text, boxWidth, fontSize);
  if (!lines) return minHeight;
  return Math.max(minHeight, lines * fontSize * lineHeight);
}

export function assertTextFits(text, boxWidth, boxHeight, fontSize, role = "text") {
  const required = requiredTextHeight(text, boxWidth, fontSize);
  const tolerance = Math.max(2, fontSize * 0.08);
  if (normalizeText(text).trim() && boxHeight + tolerance < required) {
    throw new Error(
      `${role} box too short: height=${boxHeight.toFixed(1)} required>=${required.toFixed(1)} width=${boxWidth.toFixed(1)} text=${JSON.stringify(normalizeText(text).slice(0, 80))}`,
    );
  }
}

export function boxesOverlap(a, b, padding = 0) {
  const [ax, ay, aw, ah] = a;
  const [bx, by, bw, bh] = b;
  return (
    ax + aw - padding > bx
    && bx + bw - padding > ax
    && ay + ah - padding > by
    && by + bh - padding > ay
  );
}

export function bboxContains(inner, outer, padding = 0) {
  const [ix, iy, iw, ih] = inner;
  const [ox, oy, ow, oh] = outer;
  return (
    ix >= ox + padding
    && iy >= oy + padding
    && ix + iw <= ox + ow - padding
    && iy + ih <= oy + oh - padding
  );
}

export function shouldIgnoreLayoutRole(role = "", ignoreRolePattern = DEFAULT_IGNORE_ROLE_PATTERN) {
  if (!role) return false;
  return ignoreRolePattern.test(String(role));
}

function coerceBBox(entry) {
  if (Array.isArray(entry?.bbox) && entry.bbox.length === 4) {
    return entry.bbox.map((value) => Number(value) || 0);
  }
  const x = Number(entry?.x ?? 0);
  const y = Number(entry?.y ?? 0);
  const w = Number(entry?.w ?? 0);
  const h = Number(entry?.h ?? 0);
  return [x, y, w, h];
}

function toleranceForEntry(entry) {
  const fontSize = Number(entry?.fontSize || 0);
  return Math.max(2, fontSize * 0.08);
}

export async function loadInspectArtifact(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export async function writeInspectArtifact(filePath, records, meta = {}) {
  const header = {
    kind: "deck",
    id: meta.id || "deck",
    slideSize: meta.slideSize || null,
    slideCount: meta.slideCount || null,
  };
  const lines = [header, ...records].map((entry) => JSON.stringify(entry)).join("\n") + "\n";
  await fs.writeFile(filePath, lines, "utf8");
}

export function validateLayoutRecords(records, options = {}) {
  const ignoreRolePattern = options.ignoreRolePattern || DEFAULT_IGNORE_ROLE_PATTERN;
  const overlapPadding = Number.isFinite(options.overlapPadding) ? options.overlapPadding : 2;
  const containmentPadding = Number.isFinite(options.containmentPadding) ? options.containmentPadding : 2;
  const throwOnError = options.throwOnError !== false;

  const usableRecords = records.filter((entry) => entry && entry.kind && entry.kind !== "deck");
  const byId = new Map(
    usableRecords
      .filter((entry) => entry.id)
      .map((entry) => [String(entry.id), entry]),
  );
  const textboxes = usableRecords.filter((entry) => entry.kind === "textbox");
  const issues = [];

  for (const entry of textboxes) {
    const bbox = coerceBBox(entry);
    const [x, y, w, h] = bbox;
    const fontSize = Number(entry.fontSize || 0);
    const lineHeight = Number(entry.lineHeight || 1.18);
    const minHeight = Number(entry.minHeight || 8);
    const requiredHeight = Number(entry.requiredHeight || 0) > 0
      ? Number(entry.requiredHeight || 0)
      : (fontSize > 0 ? requiredTextHeight(entry.text || "", w, fontSize, lineHeight, minHeight) : h);
    const checkFit = entry.checkFit !== false;
    const effectiveHeight = checkFit ? Math.max(h, requiredHeight) : h;
    entry._expandedBbox = [x, y, w, effectiveHeight];
    entry._requiredHeight = requiredHeight;

    if (checkFit && requiredHeight > h + toleranceForEntry(entry)) {
      issues.push(
        `slide ${entry.slide}: ${entry.role || "textbox"} needs ${Math.ceil(requiredHeight)} but only has ${Math.ceil(h)}`,
      );
    }

    if (entry.containerId) {
      const container = byId.get(String(entry.containerId));
      if (!container) {
        issues.push(`slide ${entry.slide}: ${entry.role || "textbox"} references missing container ${entry.containerId}`);
        continue;
      }
      const containerBBox = coerceBBox(container);
      const padding = Number.isFinite(entry.containerPadding) ? Number(entry.containerPadding) : containmentPadding;
      if (!bboxContains(entry._expandedBbox, containerBBox, padding)) {
        issues.push(
          `slide ${entry.slide}: ${entry.role || "textbox"} spills outside container ${container.role || entry.containerId}`,
        );
      }
    }
  }

  const bySlide = new Map();
  for (const entry of textboxes) {
    if (shouldIgnoreLayoutRole(entry.role, ignoreRolePattern)) continue;
    if (entry.checkCollision === false) continue;
    const items = bySlide.get(entry.slide) || [];
    items.push(entry);
    bySlide.set(entry.slide, items);
  }

  for (const [slide, items] of bySlide.entries()) {
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < items.length; j += 1) {
        const left = items[i];
        const right = items[j];
        const leftBox = left._expandedBbox || coerceBBox(left);
        const rightBox = right._expandedBbox || coerceBBox(right);
        if (boxesOverlap(leftBox, rightBox, overlapPadding)) {
          issues.push(`slide ${slide}: overlap between "${left.role}" and "${right.role}"`);
        }
      }
    }
  }

  const result = {
    ok: issues.length === 0,
    issues,
  };
  if (!result.ok && throwOnError) {
    throw new Error(`Layout validation failed:\n${issues.join("\n")}`);
  }
  return result;
}

export function createLayoutInspector({
  deckId = "deck",
  slideSize = { width: 1280, height: 720 },
  ignoreRolePattern = DEFAULT_IGNORE_ROLE_PATTERN,
  overlapPadding = 2,
  containmentPadding = 2,
} = {}) {
  const records = [];

  return {
    records,
    recordShape(entry) {
      const record = {
        kind: "shape",
        ...entry,
        bbox: coerceBBox(entry),
      };
      records.push(record);
      return record;
    },
    recordImage(entry) {
      const record = {
        kind: "image",
        ...entry,
        bbox: coerceBBox(entry),
      };
      records.push(record);
      return record;
    },
    recordText(entry) {
      const bbox = coerceBBox(entry);
      const [x, y, w, h] = bbox;
      const fontSize = Number(entry.fontSize || 0);
      const lineHeight = Number(entry.lineHeight || 1.18);
      const minHeight = Number(entry.minHeight || 8);
      const requiredHeight = Number(entry.requiredHeight || 0) > 0
        ? Number(entry.requiredHeight || 0)
        : (fontSize > 0 ? requiredTextHeight(entry.text || "", w, fontSize, lineHeight, minHeight) : h);
      const record = {
        kind: "textbox",
        ...entry,
        bbox,
        fontSize,
        lineHeight,
        minHeight,
        requiredHeight,
      };
      records.push(record);
      return record;
    },
    async writeInspectArtifact(filePath, meta = {}) {
      await writeInspectArtifact(filePath, records, {
        id: deckId,
        slideSize,
        ...meta,
      });
    },
    validate(extraOptions = {}) {
      return validateLayoutRecords(records, {
        ignoreRolePattern,
        overlapPadding,
        containmentPadding,
        ...extraOptions,
      });
    },
  };
}

async function main(argv) {
  const inspectPath = argv[0];
  if (!inspectPath) {
    throw new Error("Usage: node scripts/render_layout_guard.mjs /absolute/path/to/inspect.ndjson");
  }
  const resolvedPath = path.resolve(inspectPath);
  const records = await loadInspectArtifact(resolvedPath);
  validateLayoutRecords(records);
  console.log(`Layout validation passed: ${resolvedPath}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main(process.argv.slice(2))
    .then((code) => {
      process.exitCode = code;
    })
    .catch((error) => {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    });
}
