/*
test_review_app.js — headless round-trip test for review_app.js, run under
Node (no browser). Simulates the owner filling in judgments, exports to
CSV and JSON exactly as review_tool.html's export buttons would (same
functions, since review_tool.html inlines this same file's logic), then
re-imports both and checks the reconstructed state matches.

Run: node spotcheck/test_review_app.js

This test DOES NOT exercise: the actual browser DOM rendering, click
handlers, localStorage persistence, or the Blob/object-URL download
mechanism in review_tool.html — those need a real browser and were not
run headlessly (see README.md and the finetune-engineer's report for what
was and wasn't verified). What IS verified here is the thing that
actually matters for data integrity: that the export/import
serialization functions are lossless and self-consistent.
*/

const assert = require("assert");
const R = require("./review_app.js");
const sample = require("./sample_400.json");

function main() {
  console.log(`Loaded ${sample.length} examples from sample_400.json`);

  // 1. Build initial state — must be entirely empty (no pre-filled judgments).
  const initial = R.buildInitialState(sample);
  assert.strictEqual(Object.keys(initial).length, sample.length);
  for (const chunkId of Object.keys(initial)) {
    for (const field of Object.keys(initial[chunkId].fields)) {
      assert.strictEqual(
        initial[chunkId].fields[field].judgment,
        null,
        `expected null judgment at init for ${chunkId}/${field}`
      );
      assert.strictEqual(initial[chunkId].fields[field].note, "");
    }
    assert.strictEqual(initial[chunkId].example_note, "");
  }
  console.log("PASS: initial state has zero pre-filled judgments");

  // 2. Applicability matrix sanity: RISK_FACTORS never gets a sentiment
  //    field, MDA/RISK_FACTORS never get guidance_direction.
  const byId = {};
  for (const ex of sample) byId[ex.chunk_id] = ex;
  for (const ex of sample) {
    if (ex.section_type === "RISK_FACTORS") {
      assert.ok(
        !("sentiment" in initial[ex.chunk_id].fields),
        `RISK_FACTORS ${ex.chunk_id} should not have a sentiment field`
      );
    }
    if (ex.section_type === "MDA" || ex.section_type === "RISK_FACTORS") {
      assert.ok(
        !("guidance_direction" in initial[ex.chunk_id].fields),
        `${ex.section_type} ${ex.chunk_id} should not have guidance_direction`
      );
    }
  }
  console.log("PASS: applicability matrix respected (no inapplicable fields present)");

  // 3. Simulate the owner filling in judgments for a deterministic subset.
  const state = JSON.parse(JSON.stringify(initial)); // deep clone
  const judgmentCycle = ["agree", "disagree", "unsure"];
  let i = 0;
  let filledFieldCount = 0;
  for (const chunkId of Object.keys(state)) {
    const entry = state[chunkId];
    const fields = Object.keys(entry.fields);
    fields.forEach((f, fi) => {
      entry.fields[f].judgment = judgmentCycle[(i + fi) % judgmentCycle.length];
      entry.fields[f].note = fi % 2 === 0 ? `note for ${chunkId}/${f}` : "";
      filledFieldCount += 1;
    });
    if (i % 5 === 0) {
      entry.example_note = `example-level note ${i}, with a comma, and "quotes"`;
    }
    i += 1;
  }
  console.log(`Filled ${filledFieldCount} field judgments across ${i} examples`);

  // 4. Leave some judgments unfilled (missing-data path) — unset a few.
  const someIds = Object.keys(state).slice(0, 5);
  for (const chunkId of someIds) {
    const fields = Object.keys(state[chunkId].fields);
    if (fields.length > 0) {
      state[chunkId].fields[fields[0]].judgment = null;
    }
  }
  console.log("Left 5 examples' first field unfilled to test missing-data path");

  // 5. Progress computation sanity.
  const progress = R.computeProgress(state);
  assert.ok(progress.judgedFields < progress.totalFields, "expected some unfilled fields");
  console.log(`Progress: ${progress.judgedFields}/${progress.totalFields} fields judged`);
  const exProgress = R.computeExampleProgress(state);
  console.log(`Example progress: ${exProgress.done}/${exProgress.total} examples fully judged`);

  // 6. CSV round-trip.
  const csvText = R.stateToCsvString(byId, state);
  const csvLines = csvText.trim().split("\n");
  assert.strictEqual(csvLines[0], R.CSV_COLUMNS.join(","));
  const reimportedFromCsv = R.csvStringToState(csvText);
  compareStates(state, reimportedFromCsv, "CSV round-trip");
  console.log(`PASS: CSV round-trip (${csvLines.length - 1} data rows) matches original state`);

  // 7. JSON round-trip.
  const jsonText = R.stateToJsonString(state);
  const parsedJson = JSON.parse(jsonText); // must be valid JSON
  assert.strictEqual(parsedJson.format, "finscreen-spotcheck-v1");
  const reimportedFromJson = R.jsonStringToState(jsonText);
  compareStates(state, reimportedFromJson, "JSON round-trip");
  console.log("PASS: JSON round-trip matches original state exactly");

  // 8. Import-format validation: malformed JSON should raise, not silently
  //    produce an empty/garbage state.
  let threw = false;
  try {
    R.jsonStringToState(JSON.stringify({ format: "wrong-format", state: {} }));
  } catch (e) {
    threw = true;
  }
  assert.ok(threw, "expected jsonStringToState to reject wrong format");
  console.log("PASS: malformed/wrong-format JSON import is rejected, not silently accepted");

  // 9. CSV special-character escaping round-trip (commas, quotes, newlines
  //    in a note field).
  const trickyState = JSON.parse(JSON.stringify(initial));
  const firstId = Object.keys(trickyState)[0];
  const firstField = Object.keys(trickyState[firstId].fields)[0];
  trickyState[firstId].fields[firstField].judgment = "disagree";
  trickyState[firstId].fields[firstField].note =
    'a note, with a comma, a "quoted phrase", and\na newline';
  const trickyCsv = R.stateToCsvString(byId, trickyState);
  const trickyReimported = R.csvStringToState(trickyCsv);
  assert.strictEqual(
    trickyReimported[firstId].fields[firstField].note,
    trickyState[firstId].fields[firstField].note
  );
  console.log("PASS: CSV escaping round-trips commas/quotes/newlines in notes");

  console.log("\nALL TESTS PASSED");
}

function compareStates(a, b, label) {
  const aIds = Object.keys(a).sort();
  const bIds = Object.keys(b).sort();
  assert.deepStrictEqual(aIds, bIds, `${label}: chunk_id set mismatch`);
  for (const id of aIds) {
    const af = a[id].fields;
    const bf = b[id].fields;
    assert.deepStrictEqual(
      Object.keys(af).sort(),
      Object.keys(bf).sort(),
      `${label}: field set mismatch for ${id}`
    );
    for (const f of Object.keys(af)) {
      assert.strictEqual(
        af[f].judgment,
        bf[f].judgment,
        `${label}: judgment mismatch for ${id}/${f}`
      );
      assert.strictEqual(
        (af[f].note || ""),
        (bf[f].note || ""),
        `${label}: note mismatch for ${id}/${f}`
      );
    }
    assert.strictEqual(
      a[id].example_note || "",
      b[id].example_note || "",
      `${label}: example_note mismatch for ${id}`
    );
  }
}

main();
