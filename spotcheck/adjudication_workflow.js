export const meta = {
  name: 'label-adjudication',
  description: 'Third-rater adjudication of the 174 contested spot-check chunks',
  phases: [
    { title: 'Adjudicate', detail: 'one label-adjudicator per ~15-chunk batch' },
  ],
}

const FIELD_ADJ = {
  type: 'object',
  properties: {
    field: { type: 'string', enum: ['sentiment', 'guidance_direction', 'red_flags', 'distress_tier'] },
    verdict: { type: 'string', enum: ['agree', 'disagree', 'unsure'] },
    correct_label: {},
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    brief: { type: 'string' },
    pattern: { type: 'string' },
  },
  required: ['field', 'verdict', 'confidence', 'brief'],
}

const SCHEMA = {
  type: 'object',
  properties: {
    adjudications: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          chunk_id: { type: 'string' },
          fields: { type: 'array', items: FIELD_ADJ },
          needs_human: { type: 'boolean' },
          needs_human_reason: { type: 'string' },
        },
        required: ['chunk_id', 'fields', 'needs_human'],
      },
    },
  },
  required: ['adjudications'],
}

phase('Adjudicate')

function batchPrompt(path, i) {
  return `You are adjudicating batch ${i} of 12 in the FinScreen spot-check dispute resolution (HANDOFF.md §3, 2026-08-18 adjudication-delegation entry).

Steps, in order:
1. Read ${args.rubricPath} IN FULL before judging anything.
2. Read your batch file: ${path}
   Each chunk gives: chunk_id, section_type, text, high_stakes flag, and contested_fields — for each: the STORED label (bootstrap run), the blind auditor's verdict, the auditor's proposed label, and the auditor's one-sentence reason. A contested_fields entry with a "note" saying it is not contested is a high-stakes advisory case: both raters agreed, but you still adjudicate it as input for the owner.
3. For each chunk, adjudicate EVERY entry in contested_fields per your agent rules: settle the dispute on rubric merits from the passage text alone; you may side with the stored label, the auditor, or neither. Never use company identity or outside knowledge.
4. Return via structured output: one adjudications entry per chunk (exact chunk_id, in file order), with one fields entry per contested_fields entry (same field names — do not skip or add fields).

Reminders that override any instinct to be agreeable: verdict is about the STORED label (agree = stored right; disagree = stored wrong, give correct_label; unsure = rubric underdetermines — never force a call). Every high_stakes chunk gets needs_human=true no matter how clear you find it, with needs_human_reason stating what the owner must weigh. Also set needs_human=true for any unsure verdict, low confidence, or a ruling that would set a disputable precedent. Briefs must be 2-4 plain sentences a non-expert can follow, quote the passage's decisive words, and name the rubric rule that decides. Use a shared kebab-case pattern slug when chunks turn on the same recurring question.`
}

async function runBatch(path, i, expected) {
  const id = String(i).padStart(2, '0')
  const opts = { agentType: 'label-adjudicator', schema: SCHEMA, label: `adjudicate:batch_${id}`, phase: 'Adjudicate' }
  let r = await agent(batchPrompt(path, i), opts)
  if (!r || !r.adjudications || r.adjudications.length !== expected) {
    log(`batch ${id}: incomplete (${r && r.adjudications ? r.adjudications.length : 'no result'}/${expected}) — retrying once`)
    const r2 = await agent(batchPrompt(path, i), { ...opts, label: `adjudicate:batch_${id}:retry` })
    if (r2 && r2.adjudications && (!r || !r.adjudications || r2.adjudications.length >= (r.adjudications ? r.adjudications.length : 0))) r = r2
  }
  return { batch: i, adjudications: (r && r.adjudications) || [] }
}

const results = await parallel(args.batches.map((b, i) => () => runBatch(b.path, i, b.n)))

const all = results.filter(Boolean).flatMap(r => r.adjudications)
const needsHuman = all.filter(a => a.needs_human).length
log(`merged ${all.length}/174 adjudications; ${needsHuman} flagged needs_human`)
return { total: all.length, needsHuman, adjudications: all }