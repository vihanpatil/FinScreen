"""
chunk.py — Week 3 labeling-corpus builder.

Turns `data/filings.parquet` (884 rows, one row per (company, filing,
section)) into a labeling corpus of ~350-word prose windows, per the recipe
in `ROADMAP.md` §Week 3 / `DISCOVERY.md` §2.

Pipeline
--------
1. **Prose filter.** Within each section's raw text, split on `\\n` (the
   extractor emits one paragraph/table-cell/bullet per line — confirmed
   against real data: HTML tables get exploded into one-word-per-line
   fragments by `get_text()`, and a >=40-word-per-line filter cleanly drops
   that noise; see the chunking report for the verification numbers). Keep
   lines with >= 40 words as "prose paragraphs".
2. **Global exact-dedup.** Normalize each prose paragraph (whitespace
   collapse + lowercase) and dedup *across the whole corpus*, not just
   within one filing. Each unique normalized paragraph gets exactly one
   "home" occurrence (the earliest by filing_date, ticker, accession,
   in-section position — a fixed, documented tie-break) that is the one
   actually used for window-packing; every occurrence (including the home
   one) is recorded in a paragraph -> filings back-reference map, since
   Week 5 needs to know every filing a given (possibly-repeated) paragraph
   appears in, not just the one it was packed/labeled from.
3. **Window packing.** Within each section instance, walk its *home*
   paragraphs (i.e. paragraphs whose canonical/home occurrence is this
   section) in original order and accumulate them into a window until the
   running word count reaches the ~350-word target, then flush. A leftover
   partial window at section end is flushed only if it has >= 100 words
   (per the roadmap spec); a smaller remainder is dropped (unlabeled).
   Paragraphs that individually clear the 350-word target become their own
   single-paragraph window immediately.
4. **Output.** `data/labeling_corpus.parquet` — one row per chunk, with a
   stable content-derived `chunk_id`, the window text, `section_type`, and
   back-references (as list columns) to every (ticker, accession_number,
   filing_date, form) tuple any constituent paragraph appears in anywhere
   in the corpus.

Run: `python3 chunk.py`
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

FILINGS_PATH = "data/filings.parquet"
OUTPUT_CORPUS_PATH = "data/labeling_corpus.parquet"
OUTPUT_PARAGRAPH_MAP_PATH = "data/paragraph_occurrence_map.parquet"

MIN_PROSE_WORDS = 40
TARGET_WINDOW_WORDS = 350
MIN_FLUSH_WORDS = 100

_WS_RE = re.compile(r"\s+")


def normalize_paragraph(text: str) -> str:
    """Whitespace-collapse + lowercase, for exact-dedup matching only.
    Never used as the stored/labeled text — the original-cased text of the
    home occurrence is what gets packed into windows."""
    return _WS_RE.sub(" ", text.strip()).lower()


@dataclass
class ParagraphOccurrence:
    ticker: str
    cik: int
    accession_number: str
    form: str
    filing_date: str
    section_type: str
    position: int  # order within this section's prose-paragraph sequence
    text: str
    word_count: int


@dataclass
class CanonicalParagraph:
    paragraph_id: str
    normalized_text: str
    home: ParagraphOccurrence
    occurrences: list = field(default_factory=list)  # all ParagraphOccurrence, incl. home


def extract_prose_paragraphs(row) -> list[ParagraphOccurrence]:
    """Split one filings.parquet row's text on newlines, keep >=40-word lines."""
    out = []
    pos = 0
    for line in row["text"].split("\n"):
        line = line.strip()
        if not line:
            continue
        wc = len(line.split())
        if wc >= MIN_PROSE_WORDS:
            out.append(
                ParagraphOccurrence(
                    ticker=row["ticker"],
                    cik=int(row["cik"]),
                    accession_number=row["accession_number"],
                    form=row["form"],
                    filing_date=row["filing_date"],
                    section_type=row["section_type"],
                    position=pos,
                    text=line,
                    word_count=wc,
                )
            )
            pos += 1
    return out


def build_canonical_paragraphs(filings_df: pd.DataFrame) -> list[CanonicalParagraph]:
    """Extract every prose paragraph across the corpus, then collapse exact
    (normalized) duplicates into one canonical paragraph each. The "home"
    occurrence — the one actually packed into a window and thus the one
    that gets labeled — is chosen deterministically: earliest filing_date,
    then ticker, then accession_number, then in-section position. This
    means a piece of boilerplate repeated across many filings is only ever
    labeled once (via its earliest filing), while every filing that
    contains it is still recorded in the occurrence list for Week 5's
    feature-mapping needs.
    """
    all_occurrences: list[ParagraphOccurrence] = []
    for _, row in filings_df.iterrows():
        all_occurrences.extend(extract_prose_paragraphs(row))

    # Deterministic global order so "home" selection is reproducible.
    all_occurrences.sort(
        key=lambda o: (o.filing_date, o.ticker, o.accession_number, o.section_type, o.position)
    )

    by_norm: dict[str, CanonicalParagraph] = {}
    for occ in all_occurrences:
        norm = normalize_paragraph(occ.text)
        canon = by_norm.get(norm)
        if canon is None:
            pid = "P-" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]
            canon = CanonicalParagraph(paragraph_id=pid, normalized_text=norm, home=occ)
            by_norm[norm] = canon
        canon.occurrences.append(occ)

    return list(by_norm.values())


def pack_windows(canonical_paragraphs: list[CanonicalParagraph]) -> pd.DataFrame:
    """Group canonical paragraphs by their home section instance, walk each
    section's home paragraphs in original order, and pack them into
    ~350-word windows."""
    by_section: dict[tuple, list[CanonicalParagraph]] = {}
    for cp in canonical_paragraphs:
        key = (cp.home.accession_number, cp.home.section_type)
        by_section.setdefault(key, []).append(cp)

    rows = []
    for (accession_number, section_type), paras in by_section.items():
        paras.sort(key=lambda cp: cp.home.position)

        window: list[CanonicalParagraph] = []
        window_words = 0

        def flush(window, window_words):
            if not window:
                return
            para_ids = [cp.paragraph_id for cp in window]
            text = "\n\n".join(cp.home.text for cp in window)
            chunk_id = "CHK-" + hashlib.sha1("|".join(para_ids).encode("utf-8")).hexdigest()[:16]

            # Union of every filing any constituent paragraph appears in.
            src = {}
            for cp in window:
                for occ in cp.occurrences:
                    src[(occ.ticker, occ.accession_number)] = occ
            src_list = sorted(src.values(), key=lambda o: (o.filing_date, o.ticker))

            home0 = window[0].home
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "section_type": section_type,
                    "text": text,
                    "word_count": window_words,
                    "n_paragraphs": len(window),
                    "paragraph_ids": para_ids,
                    "home_ticker": home0.ticker,
                    "home_cik": home0.cik,
                    "home_accession_number": home0.accession_number,
                    "home_form": home0.form,
                    "home_filing_date": home0.filing_date,
                    "source_tickers": sorted({o.ticker for o in src_list}),
                    "source_accession_numbers": [o.accession_number for o in src_list],
                    "source_filing_dates": [o.filing_date for o in src_list],
                    "source_forms": [o.form for o in src_list],
                    "n_source_filings": len(src_list),
                }
            )

        for cp in paras:
            window.append(cp)
            window_words += cp.home.word_count
            if window_words >= TARGET_WINDOW_WORDS:
                flush(window, window_words)
                window, window_words = [], 0

        # section end: flush partial window only if >= MIN_FLUSH_WORDS
        if window and window_words >= MIN_FLUSH_WORDS:
            flush(window, window_words)
        # else: dropped, too small to be a useful labeling unit

    return pd.DataFrame(rows)


def build_paragraph_map_df(canonical_paragraphs: list[CanonicalParagraph]) -> pd.DataFrame:
    rows = []
    for cp in canonical_paragraphs:
        rows.append(
            {
                "paragraph_id": cp.paragraph_id,
                "home_accession_number": cp.home.accession_number,
                "home_section_type": cp.home.section_type,
                "word_count": cp.home.word_count,
                "n_occurrences": len(cp.occurrences),
                "occurrence_tickers": [o.ticker for o in cp.occurrences],
                "occurrence_accession_numbers": [o.accession_number for o in cp.occurrences],
            }
        )
    return pd.DataFrame(rows)


def run():
    filings_df = pd.read_parquet(FILINGS_PATH)
    print(f"Loaded {len(filings_df)} filing-section rows from {FILINGS_PATH}")

    canonical_paragraphs = build_canonical_paragraphs(filings_df)
    total_occurrences = sum(len(cp.occurrences) for cp in canonical_paragraphs)
    print(
        f"Prose paragraphs (raw, pre-dedup): {total_occurrences} | "
        f"unique (canonical) paragraphs: {len(canonical_paragraphs)} | "
        f"dedup rate: {1 - len(canonical_paragraphs)/total_occurrences:.1%}"
    )

    corpus_df = pack_windows(canonical_paragraphs)
    print(f"\nChunks produced: {len(corpus_df)}")
    print(corpus_df["section_type"].value_counts())
    print("\nword_count summary:")
    print(corpus_df["word_count"].describe())

    corpus_df.to_parquet(OUTPUT_CORPUS_PATH, index=False)
    print(f"\nWrote {OUTPUT_CORPUS_PATH}")

    para_map_df = build_paragraph_map_df(canonical_paragraphs)
    para_map_df.to_parquet(OUTPUT_PARAGRAPH_MAP_PATH, index=False)
    print(f"Wrote {OUTPUT_PARAGRAPH_MAP_PATH}")

    return corpus_df, para_map_df


if __name__ == "__main__":
    run()
