/*
review_app.js — core logic for the FinScreen spot-check review tool.

This file is written as a set of pure(ish) functions with no DOM/browser
API dependency in the functions that matter for correctness (state shape,
CSV/JSON serialization, import parsing), so it can be:
  (a) inlined into review_tool.html for the actual browser tool, and
  (b) required directly under Node for the automated round-trip test in
      test_review_app.js, without any DOM shim.

Only the functions that must touch the DOM/localStorage/Blob APIs are kept
separate (see the `wireUpDom` section notionally described in
review_tool.html's inline <script> — this file holds everything that does
NOT need a browser to be correct).
*/

(function (root) {
  "use strict";

  const FIELD_NAMES = [
    "sentiment",
    "guidance_direction",
    "red_flags",
    "distress_tier",
  ];

  // ---- state shape ----
  // For each example (by chunk_id) we track per-field judgments:
  //   { field: "agree" | "disagree" | "unsure" | null, note: string }
  // plus one example-level free-text note.
  // Judgments start EMPTY (null) — never pre-filled.
  function emptyJudgmentForExample(example) {
    const perField = {};
    for (const f of FIELD_NAMES) {
      if (example.applicability[f]) {
        perField[f] = { judgment: null, note: "" };
      }
    }
    // red_flags/distress_tier are list-valued; if the labeling itself
    // failed (parse_ok=False) there is nothing to judge — that field is
    // still "applicable" per section_type but has no content, so the UI
    // must say "labeling failed" rather than implying an empty list was
    // asserted by the model.
    return {
      chunk_id: example.chunk_id,
      fields: perField,
      example_note: "",
    };
  }

  function buildInitialState(examples) {
    const state = {};
    for (const ex of examples) {
      state[ex.chunk_id] = emptyJudgmentForExample(ex);
    }
    return state;
  }

  // ---- CSV export ----
  // One row per (chunk_id, field) that is applicable for that chunk's
  // section_type. Columns:
  //   chunk_id, section_type, primary_tier, field, judgment, field_note, example_note
  const CSV_COLUMNS = [
    "chunk_id",
    "section_type",
    "primary_tier",
    "field",
    "judgment",
    "field_note",
    "example_note",
  ];

  function csvEscape(value) {
    if (value === null || value === undefined) return "";
    const s = String(value);
    if (/[",\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function stateToCsvRows(examplesById, state) {
    const rows = [CSV_COLUMNS.join(",")];
    for (const chunkId of Object.keys(state)) {
      const ex = examplesById[chunkId];
      const entry = state[chunkId];
      for (const field of Object.keys(entry.fields)) {
        const fj = entry.fields[field];
        rows.push(
          [
            chunkId,
            ex.section_type,
            ex.primary_tier,
            field,
            fj.judgment === null ? "" : fj.judgment,
            fj.note || "",
            entry.example_note || "",
          ]
            .map(csvEscape)
            .join(",")
        );
      }
    }
    return rows;
  }

  function stateToCsvString(examplesById, state) {
    return stateToCsvRows(examplesById, state).join("\n") + "\n";
  }

  // Minimal, dependency-free CSV parser sufficient for our own export
  // format (handles quoted fields with embedded commas/newlines/quotes).
  function parseCsv(text) {
    const rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;
    let i = 0;
    const n = text.length;
    while (i < n) {
      const c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') {
            field += '"';
            i += 2;
            continue;
          } else {
            inQuotes = false;
            i += 1;
            continue;
          }
        } else {
          field += c;
          i += 1;
          continue;
        }
      } else {
        if (c === '"') {
          inQuotes = true;
          i += 1;
          continue;
        } else if (c === ",") {
          row.push(field);
          field = "";
          i += 1;
          continue;
        } else if (c === "\n") {
          row.push(field);
          rows.push(row);
          row = [];
          field = "";
          i += 1;
          continue;
        } else if (c === "\r") {
          i += 1;
          continue;
        } else {
          field += c;
          i += 1;
          continue;
        }
      }
    }
    if (field.length > 0 || row.length > 0) {
      row.push(field);
      rows.push(row);
    }
    return rows;
  }

  function csvStringToState(csvText) {
    const rows = parseCsv(csvText);
    if (rows.length === 0) return {};
    const header = rows[0];
    const idx = {};
    header.forEach((h, i) => (idx[h] = i));
    const state = {};
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r];
      if (row.length === 1 && row[0] === "") continue; // trailing blank line
      const chunkId = row[idx.chunk_id];
      const field = row[idx.field];
      const judgment = row[idx.judgment];
      const fieldNote = row[idx.field_note];
      const exampleNote = row[idx.example_note];
      if (!state[chunkId]) {
        state[chunkId] = { chunk_id: chunkId, fields: {}, example_note: exampleNote || "" };
      }
      state[chunkId].fields[field] = {
        judgment: judgment === "" ? null : judgment,
        note: fieldNote || "",
      };
      if (exampleNote) state[chunkId].example_note = exampleNote;
    }
    return state;
  }

  // ---- JSON export/import ----
  function stateToJsonObject(state) {
    return { format: "finscreen-spotcheck-v1", state: state };
  }

  function stateToJsonString(state) {
    return JSON.stringify(stateToJsonObject(state), null, 1);
  }

  function jsonStringToState(jsonText) {
    const obj = JSON.parse(jsonText);
    if (!obj || typeof obj !== "object") {
      throw new Error("Invalid JSON import: not an object");
    }
    if (obj.format !== "finscreen-spotcheck-v1") {
      throw new Error(
        "Invalid JSON import: unrecognized format '" + obj.format + "'"
      );
    }
    if (!obj.state || typeof obj.state !== "object") {
      throw new Error("Invalid JSON import: missing 'state'");
    }
    return obj.state;
  }

  // ---- progress ----
  function computeProgress(state) {
    let total = 0;
    let judged = 0;
    for (const chunkId of Object.keys(state)) {
      const entry = state[chunkId];
      for (const field of Object.keys(entry.fields)) {
        total += 1;
        if (entry.fields[field].judgment !== null) judged += 1;
      }
    }
    return { judgedFields: judged, totalFields: total };
  }

  // Per-EXAMPLE completion (used for the n/400 counter): an example counts
  // as "done" if every applicable field for it has a non-null judgment.
  function computeExampleProgress(state) {
    let total = 0;
    let done = 0;
    for (const chunkId of Object.keys(state)) {
      total += 1;
      const entry = state[chunkId];
      const fields = Object.keys(entry.fields);
      const allJudged = fields.every((f) => entry.fields[f].judgment !== null);
      if (allJudged) done += 1;
    }
    return { done, total };
  }

  const api = {
    FIELD_NAMES,
    CSV_COLUMNS,
    emptyJudgmentForExample,
    buildInitialState,
    csvEscape,
    stateToCsvRows,
    stateToCsvString,
    parseCsv,
    csvStringToState,
    stateToJsonObject,
    stateToJsonString,
    jsonStringToState,
    computeProgress,
    computeExampleProgress,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.FinScreenReview = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
