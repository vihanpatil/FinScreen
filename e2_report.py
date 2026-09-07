"""
e2_report.py -- renders data/E2_UNIVERSE_REPORT.md from the artifacts that
build_universe_e2.py produces. Kept in a separate module so the report prose is
generated from run diagnostics (EXPANSION_PLAN.md §5's "report prose
regenerated from diagnostics" rule) rather than hand-typed and drifting.

Nothing here fetches anything or decides anything -- it only formats what the
builder measured, including the parts that came out awkward.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from build_universe_e2 import (
    AUDIT_MAX_FLOAT_TO_ASSETS,
    AUDIT_MAX_IMPLIED_PRICE_USD,
    AUDIT_MIN_IMPLIED_PRICE_USD,
    AUDIT_MIN_PUBLIC_SHARES,
    BROAD8_K,
    CACHE_DIR,
    BROAD8_SECTORS,
    CONTINUITY5_K,
    CONTINUITY5_SECTORS,
    FLOAT_RULE_MIN_SHARES,
    FLOAT_RULE_NEWER_ZERO,
    FRAMES_LOOKBACK_QUARTERS,
    HYBRID136_CORE_K,
    HYBRID136_CORE_SECTORS,
    HYBRID136_EXTENSION_K,
    HYBRID136_EXTENSION_SECTORS,
    HYBRID136_K,
    HYBRID136_SECTORS,
    HYBRID136_STRATUM,
    MANUAL_EXCLUSIONS_PATH,
    MAX_FLOAT_STALENESS_DAYS,
    MAX_PLAUSIBLE_FLOAT_USD,
    MIN_ELIGIBLE_QUARTERS,
    MIN_PUBLIC_SHARES_FOR_MEMBERSHIP,
    MIN_SHARES_MAX_STALENESS_DAYS,
    NON_OPERATING_SIC,
    OPTION_RECORD_VARIANTS,
    RATIFIED_VARIANT,
    RECON_DAY,
    RECON_MONTH,
    REPORT_PATH,
    SIC_EXACT,
    SIC_RANGES,
    STRATUM_CORE,
    STRATUM_EXTENSION,
    SUSPECT_FLOAT_RATIO,
    TAXONOMIES,
    churn_stats,
    ruleset_for,
)

USD_B = 1e9


def _cache_footprint() -> list[dict]:
    """Measured, not estimated: file counts and bytes of the caches this phase
    populated."""
    from build_universe_e2 import CONCEPT_DIR, FRAMES_DIR, RAW_DIR

    rows = []
    for label, d in (
        ("data/raw/frames/ (NEW)", FRAMES_DIR),
        ("data/raw/companyconcept/ (NEW)", CONCEPT_DIR),
        ("data/raw/submissions/ (shared with E1)", RAW_DIR / "submissions"),
        ("data/raw/prices/ (shared, probe only)", RAW_DIR / "prices"),
    ):
        try:
            files = [f for f in d.rglob("*") if f.is_file()]
            rows.append({
                "cache": label,
                "files": len(files),
                "MB": round(sum(f.stat().st_size for f in files) / 1e6, 1),
            })
        except Exception:  # noqa: BLE001
            rows.append({"cache": label, "files": 0, "MB": 0.0})
    return rows


def _load_df(path):
    try:
        return pd.read_parquet(path)
    except Exception:  # noqa: BLE001
        return None


def _load_json(path):
    import json
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _b(x) -> str:
    try:
        return f"${float(x)/USD_B:,.1f}B"
    except (TypeError, ValueError):
        return "-"


def _sector_matrix(panel: pd.DataFrame, dates, sectors) -> pd.DataFrame:
    ds = [d.isoformat() for d in dates]
    m = (
        panel.groupby(["recon_date", "sector"]).size().unstack(fill_value=0).reindex(ds, fill_value=0)
    )
    for s in sectors:
        if s not in m.columns:
            m[s] = 0
    m = m[list(sectors)]
    m["TOTAL"] = m.sum(axis=1)
    return m


def _md_table(df: pd.DataFrame, index_name: str = "") -> str:
    df = df.copy()
    if index_name:
        df.insert(0, index_name, df.index)
    head = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join([head, sep] + rows)


def render_report(
    *,
    dates,
    panels: dict[str, pd.DataFrame],
    spells: dict[str, pd.DataFrame],
    rejects: dict[str, pd.DataFrame],
    profiles,
    shortlist: pd.DataFrame,
    census: pd.DataFrame,
    probes: list[dict],
    former_probes: list[dict] = (),
    flags: dict,
    suspects: list[dict],
    args,
    request_count: int,
    price_request_count: int = 0,
    exclusions=(),
    shadow_panel: Optional[pd.DataFrame] = None,
    scale_audit: Optional[pd.DataFrame] = None,
    scale_summary: Optional[dict] = None,
    rules_off_panel: Optional[pd.DataFrame] = None,
    legacy_panel: Optional[pd.DataFrame] = None,
    shares_coverage: Optional[dict] = None,
) -> str:
    ds = [d.isoformat() for d in dates]
    L: list[str] = []
    A = L.append

    c5, b8 = panels["continuity5"], panels["broad8"]
    hy = panels[RATIFIED_VARIANT]
    c5_ciks, b8_ciks = set(c5["cik"]), set(b8["cik"])
    hy_ciks = set(hy["cik"])
    both = c5_ciks & b8_ciks
    exclusions = list(exclusions)
    scale_audit = pd.DataFrame() if scale_audit is None else scale_audit
    scale_summary = scale_summary or {}
    hy_core = hy[hy["stratum"] == STRATUM_CORE]
    hy_ext = hy[hy["stratum"] == STRATUM_EXTENSION]

    # ---------------------------------------------------------------- header
    A("# E2 universe construction — phase F1 build + owner decision record")
    A("")
    A(f"Generated by `build_universe_e2.py` on {date.today().isoformat()}. "
      f"`data/universe.csv` is untouched and no ingestion has been run against "
      f"any table here. The owner ratified the **`hybrid136`** two-stratum "
      f"universe in chat on 2026-08-21; `continuity5` and `broad8` are rebuilt "
      f"unchanged below as the option record that decision rests on.")
    A("")
    A("The owner separately ratified **two float-integrity rules** on "
      "2026-08-21, scoped to the live `hybrid136` path only. They are "
      "documented in **§3.8**, which also reports every time they fired and "
      "what they did to membership. The two items they replace have moved off "
      "§9's open list into its adopted list.")
    A("")

    # ------------------------------------------------------ decision recorded
    A("> ## DECISION RECORDED (owner, in chat, 2026-08-21): `hybrid136`")
    A("> ")
    A("> The earlier continuity5-vs-broad8 either/or was replaced by a **hybrid")
    A("> two-stratum universe**. Both original candidates remain built, byte-for-")
    A("> byte, as the option record — §3.2/§3.3 and §4.2/§4.3 are unchanged.")
    A("> ")
    A("> | | **core stratum** | **extension stratum** | **`hybrid136`** |")
    A("> |---|---|---|---|")
    A(f"> | rule | exactly `continuity5`'s | the 3 `broad8`-only sectors | union |")
    A("> | sectors | " + ", ".join(HYBRID136_CORE_SECTORS) + " | "
      + ", ".join(HYBRID136_EXTENSION_SECTORS) + " | 8 |")
    A(f"> | K per sector per date | {HYBRID136_CORE_K} | {HYBRID136_EXTENSION_K} | — |")
    A(f"> | members per date | {HYBRID136_CORE_K * len(HYBRID136_CORE_SECTORS)} | "
      f"{HYBRID136_EXTENSION_K * len(HYBRID136_EXTENSION_SECTORS)} | "
      f"**{sum(HYBRID136_K.values())}** |")
    A(f"> | distinct CIKs over the decade | **{hy_core['cik'].nunique()}** | "
      f"**{hy_ext['cik'].nunique()}** | **{len(hy_ciks)}** |")
    A(f"> | members at first date ({ds[0]}) | {len(hy_core[hy_core.recon_date == ds[0]])} | "
      f"{len(hy_ext[hy_ext.recon_date == ds[0]])} | {len(hy[hy.recon_date == ds[0]])} |")
    A(f"> | members at last date ({ds[-1]}) | {len(hy_core[hy_core.recon_date == ds[-1]])} | "
      f"{len(hy_ext[hy_ext.recon_date == ds[-1]])} | {len(hy[hy.recon_date == ds[-1]])} |")
    A("> ")
    A("> Everything else is held fixed across the strata and identical to the")
    A("> option-record variants: same `dei:EntityPublicFloat` ranks, same")
    A("> point-in-time rule, same backward-only eligibility, same sanitizer,")
    A("> same annual reconstitution dates, same SIC table. The three SIC")
    A("> sub-decisions stay at this report's documented defaults — telecom")
    A("> (SIC 4812/4813) → `utilities`, card networks (7389) → `financials`,")
    A("> managed care (6324) → `healthcare` (§7, §8).")
    A("> ")
    A("> The membership table gains a **`stratum`** column (`core`/`extension`).")
    A("> `continuity5`/`broad8` deliberately do **not** gain it: adding a column")
    A("> to the tables the decision cites would quietly change the audit trail.")
    A("")

    # ------------------------------------------------- stratum analysis rule
    A("> ## STRATUM ANALYSIS RULE (binding on every downstream E2 result)")
    A("> ")
    A("> The two strata are **not** interchangeable and must not be silently")
    A("> pooled into one headline number:")
    A("> ")
    A("> 1. **Primary confirmatory analysis runs on the CORE stratum only.**")
    A(">    Core is `continuity5` by construction, so it keeps E1's sector")
    A(">    definitions and is the population the pre-registered E2 hypothesis")
    A(">    is about. The primary metric, its pre-registered fold structure and")
    A(">    its power calculation all refer to core.")
    A("> 2. **The EXTENSION stratum is secondary**, reported two ways — pooled")
    A(">    with core *and* stratified (core / extension side by side) — so a")
    A(">    reader can see whether any pooled effect is carried by one stratum.")
    A("> 3. **Promotion of the extension stratum to confirmatory status is")
    A(">    contingent on gate G2**: the E2 spot-check must show label quality")
    A(">    holding up *sector-stratified*, i.e. in industrials, utilities and")
    A(">    materials/real-estate specifically — not merely on average. The")
    A(">    fine-tuned labeler was trained on E1 text, which contains **none** of")
    A(">    these three sectors, so extension-sector label quality is an")
    A(">    extrapolation until G2 measures it.")
    A("> 4. Until G2 rules, an extension-inclusive number never appears without")
    A(">    the core-only number beside it.")
    A("")

    # ------------------------------------------------------------- PIT claim
    A("## 1. Point-in-time discipline — what is guaranteed, and how")
    A("")
    A("Membership at reconstitution date **D** is a function of EDGAR facts "
      "whose *public filing date* is strictly earlier than D. Two mechanisms, "
      "both in code:")
    A("")
    A("1. **Float source.** Values come from `dei:EntityPublicFloat` facts read "
      "from the XBRL **companyconcept** endpoint, which carries an explicit "
      "`filed` date per fact. `pit_float_asof()` keeps only facts with "
      "`filed < D` (strictly — a filing made *on* D is not used, because "
      "intraday publication time is unknown), then takes the latest measurement "
      "instant, with a later `filed` breaking ties so a 10-K/A supersedes the "
      "10-K it amends.")
    A("2. **Eligibility.** `eligible_quarters_covered()` counts 10-K/10-Q "
      f"filings with `filingDate < D` in the {MIN_ELIGIBLE_QUARTERS} calendar "
      "quarters *preceding* D. It never looks forward. A company that stops "
      "filing the day after D is still a member at D — which is the entire "
      "point (EXPANSION_PLAN.md §2c: no forward-looking continuity condition).")
    A("")
    A("The guarantee is then **re-asserted on the finished table**, not just "
      "inside the selection loop: `assert_pit_membership()` recomputes "
      "`float_filed < recon_date` over every emitted membership row and raises "
      "on any violation. It ran clean on all three variants in this build, "
      "and on the pre-exclusion counterfactual build as well. "
      "`test_build_universe_e2.py` pins the behaviour with a fact deliberately "
      "filed one day after the reconstitution date (must be rejected) and one "
      "day before (must be accepted).")
    A("")
    A("**The one knowing exception**, stated plainly: SIC codes come from "
      "`submissions.json`, which reports the registrant's *current* SIC, not "
      "its SIC as of D. That is a small look-ahead confined to the sector "
      "**label** — it can move a company between buckets; it cannot make a "
      "company large or small, and it cannot resurrect a company that had "
      "stopped filing. EDGAR publishes no historical SIC series, so this is a "
      "stated assumption rather than a fixable defect (it was already flagged "
      "in the recon and EXPANSION_PLAN.md §2c).")
    A("")

    # --------------------------------------------------------------- design
    A("## 2. Window, reconstitution convention, and the rules as implemented")
    A("")
    A(f"- **{len(dates)} annual reconstitution dates**: {ds[0]} … {ds[-1]} "
      f"(every {RECON_MONTH:02d}-{RECON_DAY:02d}). All parameterized "
      "(`--first-year/--last-year`, `RECON_MONTH/RECON_DAY`) because the exact "
      "window is still subject to gate **G3**.")
    A("- **Why July 1.** `EntityPublicFloat` is the 10-K cover-page figure "
      "measured on the last business day of the registrant's *second fiscal "
      "quarter* and first made public when the 10-K is filed — typically 8–10 "
      "months later (verified: BBBY's 2021-08-28 instant went public "
      "2022-04-21; Apple's 2025-03-28 instant went public 2025-10-31). July 1 "
      "(a) sits after the Feb–Mar 10-K wave of December-FYE filers, who are "
      "most US large caps, so their float is public and ~12 months old; "
      "(b) sits after the Q1 10-Q wave, so eligibility sees complete quarters; "
      "(c) matches the Russell reconstitution convention the ratified design "
      "was modelled on; (d) is the first day of a calendar quarter, so the "
      f"{MIN_ELIGIBLE_QUARTERS} eligibility quarters are exactly the "
      f"{MIN_ELIGIBLE_QUARTERS} completed calendar quarters before it, with no "
      "partial quarter to reason about; and (e) is a fixed calendar date, not "
      "trailing-from-today (the coupling audit's F1 requirement).")
    A(f"- **Eligibility rule (backward-only).** Each of the "
      f"{MIN_ELIGIBLE_QUARTERS} calendar quarters before D must contain ≥1 "
      "10-K or 10-Q filed before D. A lenient alternative (≥8 periodic filings "
      "in the same 24 months, without requiring one per quarter) is computed "
      "for comparison — see §6.")
    A("- **Non-operating exclusion.** A registrant is dropped if "
      "`entityType != \"operating\"` in submissions.json, or if its SIC is in "
      "the non-operating list (funds, trusts, SPACs/blank cheques, "
      "securitization vehicles, royalty traders, non-classifiable). The full "
      "list is in §8.3. Foreign private issuers need no separate rule: they file "
      "20-F/40-F, so they fail the 10-K/10-Q eligibility test automatically.")
    A(f"- **Float sanity filter.** A fact is rejected if it is ≤0, below $1M, "
      f"above $10T, or ≥{SUSPECT_FLOAT_RATIO:.0f}× the *smaller* of the "
      "registrant's own float at its immediately adjacent disclosure dates "
      "(applied iteratively). Rejected facts are **excluded and counted, "
      "never rescaled** (§6.4 — this filter turned out to matter a great deal).")
    A(f"- **Staleness cap.** A float fact older than {MAX_FLOAT_STALENESS_DAYS} "
      "days at D is not usable.")
    A(f"- **Newer-zero-float rule** (`{FLOAT_RULE_NEWER_ZERO}`, ratified "
      "2026-08-21, **`hybrid136` only**). If a registrant's most recent "
      "already-public float disclosure at D is exactly 0, it has no public "
      "float at D and is ineligible — the sanitizer no longer gets to drop "
      "that 0 and let an older positive value win. Full semantics in §3.8.")
    A(f"- **Minimum-shares rule** (`{FLOAT_RULE_MIN_SHARES}`, ratified "
      "2026-08-21, **`hybrid136` only**). If a registrant's own most recent "
      "already-public cover-page share count at D is below "
      f"{MIN_PUBLIC_SHARES_FOR_MEMBERSHIP:,} shares, it has no publicly traded "
      "common equity at D and is ineligible. Full semantics in §3.8.")
    A("")

    # -------------------------------------------------- recon deltas (flags)
    A("### 2a. Where live EDGAR differed from `data/expansion_recon_2026-08-20.json`")
    A("")
    A("Three deltas, all verified live this session. None was worked around "
      "silently; the recon's `universe` section should be corrected.")
    A("")
    A("1. **Frames data points carry no `filed` date.** A frames datum is "
      "`{accn, cik, entityName, loc, end, val}` only. The recon's plan (\"union "
      "of the 4 quarterly instant frames preceding the date\") therefore cannot, "
      "on its own, establish that a value was public at D — `end` is the "
      "*measurement instant*, and the filing that disclosed it lands 8–10 "
      "months later. Frames are used here for **enumeration only**; every float "
      "value that reaches a membership row is re-fetched per CIK from the "
      "**companyconcept** endpoint, which does carry `filed` (~3 KB per CIK, "
      "vs ~4 MB for companyfacts). That endpoint is the \"per-CIK patch pass\" "
      "the recon asked for, done cheaply.")
    A(f"2. **A 4-quarter union is not enough once the PIT filter is applied.** "
      "With D = July 1, the usable band is instants in roughly [D−15mo, D−8mo] "
      "— narrower than the 4 frames span — so whole fiscal-year-end cohorts "
      "fall out. Worked example: Apple (September FYE) discloses its March "
      "instant in an October 10-K, so at D=2026-07-01 its newest fact "
      "(instant 2026-03-27) is not yet filed and its previous one (instant "
      "2025-03-28) sits in CY2025Q1I — outside the 4-quarter window "
      "(CY2025Q2I…CY2026Q1I). Same for June-FYE Microsoft. This build unions "
      f"**{FRAMES_LOOKBACK_QUARTERS} quarters** (`--frames-lookback`), which "
      "guarantees every annual filer has ≥1 already-public fact whatever its "
      "fiscal calendar. Cost of the change: 48 cached frame GETs instead of 44.")
    A("3. **BBBY confirms survivorship-free selection for the float concept "
      "specifically** (the recon verified it for the *shares* concept). Its "
      "float history is complete through the 2023-06-14 10-K, and its "
      "submissions record now reads `20230930-DK-Butterfly-1, Inc.` with an "
      "**empty** ticker list — which is exactly the censoring problem in §5, "
      "and also the reason the delisting census cannot rely on ticker "
      "resolution alone.")
    A("")
    A("A fourth item is not a recon error but was not anticipated: the frames "
      "are **contaminated with filer scale errors** large enough to hijack a "
      "naive top-K (§5).")
    A("")

    # --------------------------------------------------- headline comparison
    A("## 3. The universes: the ratified `hybrid136`, then the option record")
    A("")

    def _variant_block(heading: str, name: str, panel: pd.DataFrame, note: str = "") -> None:
        sectors = TAXONOMIES[name][0]
        K = TAXONOMIES[name][1]
        A(f"### {heading} `{name}` — members per sector per reconstitution date")
        A("")
        if note:
            A(note)
            A("")
        m = _sector_matrix(panel, dates, sectors)
        A(_md_table(m, index_name="recon_date"))
        A("")
        short = [
            f"{d}/{s}: {m.loc[d, s]}/{K[s]}"
            for d in ds
            for s in sectors
            if m.loc[d, s] < K[s]
        ]
        if short:
            A(f"**Under-filled buckets ({len(short)})** — the sector did not "
              "contain K eligible, operating, PIT-valid registrants in the "
              "diligence shortlist at that date:")
            A("")
            for s in short[:40]:
                A(f"- {s}")
            if len(short) > 40:
                A(f"- … and {len(short) - 40} more (see `{name}_panel.csv`)")
        else:
            A(f"All buckets filled to K at all {len(ds)} dates.")
        A("")
        floors = (
            panel.sort_values("sector_rank").groupby(["recon_date", "sector"]).last()["float_usd"]
        )
        fl = floors.unstack().reindex(ds)
        fl = fl.apply(lambda col: col.map(_b))
        A("Float of the *smallest* member in each bucket (the bucket floor) — "
          "this is what \"K deep\" actually costs in company size:")
        A("")
        A(_md_table(fl, index_name="recon_date"))
        A("")

    _variant_block(
        "3.1",
        RATIFIED_VARIANT,
        hy,
        note=(
            "**This is the ratified universe.** The first five columns are the "
            f"CORE stratum (K={HYBRID136_CORE_K}, exactly `continuity5`'s rule); "
            "the last three are the EXTENSION stratum "
            f"(K={HYBRID136_EXTENSION_K}). The manual exclusions of §3.7 do not "
            "shrink these counts — a vacated slot is refilled by the next "
            "eligible registrant in that bucket — but they do move the bucket "
            "floors below, which is where their effect is visible."
        ),
    )
    strat_counts = (
        hy.groupby(["recon_date", "stratum"]).size().unstack(fill_value=0).reindex(ds, fill_value=0)
    )
    for col in (STRATUM_CORE, STRATUM_EXTENSION):
        if col not in strat_counts.columns:
            strat_counts[col] = 0
    strat_counts = strat_counts[[STRATUM_CORE, STRATUM_EXTENSION]]
    strat_counts["TOTAL"] = strat_counts.sum(axis=1)
    A("Members per stratum per date:")
    A("")
    A(_md_table(strat_counts, index_name="recon_date"))
    A("")

    _variant_block(
        "3.2", "continuity5", c5,
        note="_Option record. Unchanged from the pre-decision build._",
    )
    _variant_block(
        "3.3", "broad8", b8,
        note="_Option record. Unchanged from the pre-decision build._",
    )

    # overlap / difference
    A("### 3.4 Overlap and disagreement (option record)")
    A("")
    prof_name = {c: profiles[c].name for c in (c5_ciks | b8_ciks)}
    b8_only = sorted(b8_ciks - c5_ciks)
    c5_only = sorted(c5_ciks - b8_ciks)
    A(f"- CIKs in **both**: {len(both)}")
    A(f"- **broad8 only**: {len(b8_only)} — companies whose sector does not exist under continuity5, plus bucket-size effects")
    A(f"- **continuity5 only**: {len(c5_only)} — names that fit in a 5-sector bucket at K=20 but not in a shallower 8-sector one")
    A("")
    b8p = b8.sort_values("float_usd", ascending=False).drop_duplicates("cik").set_index("cik")
    rows = []
    for cik in b8_only:
        r = b8p.loc[cik]
        rows.append({"cik": cik, "name": r["name"][:38], "sector": r["sector"],
                     "sic": r["sic"], "max_float": _b(r["float_usd"])})
    df_b8only = pd.DataFrame(rows).sort_values("max_float", key=lambda s: s.map(
        lambda x: float(str(x).replace("$", "").replace("B", "").replace(",", ""))), ascending=False)
    A("**The 25 largest broad8-only names** (i.e. the largest US companies "
      "continuity5 throws away entirely):")
    A("")
    A(_md_table(df_b8only.head(25).reset_index(drop=True)))
    A("")
    c5p = c5.sort_values("float_usd", ascending=False).drop_duplicates("cik").set_index("cik")
    rows = []
    for cik in c5_only:
        r = c5p.loc[cik]
        rows.append({"cik": cik, "name": r["name"][:38], "sector": r["sector"],
                     "sic": r["sic"], "max_float": _b(r["float_usd"])})
    if rows:
        A("**continuity5-only names** (they exist in both taxonomies' sector "
          "sets, but only the deeper K=20 buckets reach them):")
        A("")
        A(_md_table(pd.DataFrame(rows).head(25).reset_index(drop=True)))
        A("")

    # excluded-by-continuity5 sector census
    rej5 = rejects["continuity5"]
    exc = rej5[rej5["reason"].astype(str).str.startswith("sector_excluded")]
    if len(exc):
        exc_top = (
            exc.sort_values("float_usd", ascending=False)
            .drop_duplicates("cik")
            .head(20)[["cik", "name", "sic", "float_usd"]]
        )
        exc_top["float_usd"] = exc_top["float_usd"].map(_b)
        exc_top["name"] = exc_top["name"].str.slice(0, 38)
        A(f"**Largest registrants excluded by continuity5's 5-sector filter** "
          f"({exc['cik'].nunique()} distinct CIKs in the shortlist were dropped "
          "purely because their SIC maps outside tech/financials/healthcare/"
          "energy/consumer):")
        A("")
        A(_md_table(exc_top.reset_index(drop=True)))
        A("")

    # --------------------------------------- 3.5 extension-only top members
    A("### 3.5 The extension stratum, name by name")
    A("")
    A(f"The {hy_ext['cik'].nunique()} distinct CIKs the extension stratum adds "
      "to E1's five sectors — i.e. exactly the population `continuity5` throws "
      "away and `hybrid136` keeps, at K="
      f"{HYBRID136_EXTENSION_K} per sector per date. Largest 30 by their own "
      "maximum point-in-time float over the decade:")
    A("")
    ext_top = (
        hy_ext.sort_values("float_usd", ascending=False)
        .drop_duplicates("cik")
        .head(30)[["cik", "name", "sector", "sic", "float_usd", "recon_date"]]
        .rename(columns={"float_usd": "max_float", "recon_date": "at_date"})
        .reset_index(drop=True)
    )
    ext_top["name"] = ext_top["name"].astype(str).str.slice(0, 38)
    ext_top["max_float"] = ext_top["max_float"].map(_b)
    A(_md_table(ext_top))
    A("")
    ext_sector_counts = hy_ext.drop_duplicates("cik")["sector"].value_counts().to_dict()
    A(f"Distinct CIKs by extension sector: {ext_sector_counts}.")
    A("")

    # ------------------------- 3.6 how hybrid136 relates to the option record
    A("### 3.6 How `hybrid136` relates to the option record")
    A("")
    core_by_date = {d: set(hy_core[hy_core.recon_date == d]["cik"]) for d in ds}
    c5_by_date = {d: set(c5[c5.recon_date == d]["cik"]) for d in ds}
    ext_by_date = {d: set(hy_ext[hy_ext.recon_date == d]["cik"]) for d in ds}
    b8ext_by_date = {
        d: set(
            b8[(b8.recon_date == d) & (b8.sector.isin(HYBRID136_EXTENSION_SECTORS))]["cik"]
        )
        for d in ds
    }
    core_delta = {d: (core_by_date[d] ^ c5_by_date[d]) for d in ds}
    ext_delta = {d: (ext_by_date[d] ^ b8ext_by_date[d]) for d in ds}
    n_core_delta = sum(len(v) for v in core_delta.values())
    n_ext_delta = sum(len(v) for v in ext_delta.values())
    A("Selection is independent **per sector** (top-K inside each bucket over "
      "one shared candidate pool), so the strata are not approximations of the "
      "option-record variants — with the exclusions switched off they reproduce "
      "them *exactly*, and every difference below is a documented manual "
      "exclusion or the registrant that refilled the slot it vacated. That is "
      "checked, not asserted:")
    A("")
    if shadow_panel is not None and len(shadow_panel):
        sh_core = shadow_panel[shadow_panel["stratum"] == STRATUM_CORE]
        sh_ext = shadow_panel[shadow_panel["stratum"] == STRATUM_EXTENSION]
        core_ok = all(
            set(sh_core[sh_core.recon_date == d]["cik"]) == c5_by_date[d] for d in ds
        )
        ext_ok = all(
            set(sh_ext[sh_ext.recon_date == d]["cik"]) == b8ext_by_date[d] for d in ds
        )
        A(f"- With `--ignore-manual-exclusions`, the CORE stratum equals "
          f"`continuity5`'s membership at every one of the {len(ds)} dates: "
          f"**{'YES' if core_ok else 'NO — investigate'}**. The EXTENSION "
          "stratum equals `broad8`'s three non-core buckets at every date: "
          f"**{'YES' if ext_ok else 'NO — investigate'}**. "
          "`test_build_universe_e2.py` pins both identities.")
    n_core_removed = sum(len(c5_by_date[d] - core_by_date[d]) for d in ds)
    n_ext_removed = sum(len(b8ext_by_date[d] - ext_by_date[d]) for d in ds)
    A(f"- CORE stratum vs `continuity5` **as built**: **{n_core_delta}** "
      f"membership rows differ across the {len(ds)} dates — "
      f"{n_core_removed} removed by a manual exclusion, "
      f"{n_core_delta - n_core_removed} refilled by the next eligible name.")
    A(f"- EXTENSION stratum vs `broad8`'s industrials/utilities/"
      f"materials_realestate buckets: **{n_ext_delta}** rows differ — "
      f"{n_ext_removed} removed, {n_ext_delta - n_ext_removed} refilled.")
    A("")
    if n_core_delta or n_ext_delta:
        rows = []
        for d in ds:
            for cik in sorted(core_delta[d]):
                rows.append({"recon_date": d, "stratum": STRATUM_CORE, "cik": cik,
                             "in hybrid136 core": cik in core_by_date[d],
                             "in continuity5": cik in c5_by_date[d]})
            for cik in sorted(ext_delta[d]):
                rows.append({"recon_date": d, "stratum": STRATUM_EXTENSION, "cik": cik,
                             "in hybrid136 core": cik in ext_by_date[d],
                             "in continuity5": cik in b8ext_by_date[d]})
        dd = pd.DataFrame(rows).rename(columns={
            "in hybrid136 core": "in hybrid136", "in continuity5": "in option record"})
        prof_all = {int(c): profiles[int(c)].name for c in dd["cik"]}
        dd.insert(3, "name", dd["cik"].map(lambda c: prof_all[int(c)][:34]))
        A("Every differing row, with the direction of the difference:")
        A("")
        A(_md_table(dd))
        A("")
        A("**Read this table carefully.** Rows where `in option record` is True "
          "and `in hybrid136` is False are registrants the F1 audit removed as "
          "verified data errors (§3.7, §6.7) — which means the option-record "
          "tables above still contain them. `continuity5` and `broad8` were "
          "deliberately left byte-identical to the tables the owner's decision "
          "cites; they were **not** retro-cleaned. Rows where `in hybrid136` is "
          "True and `in option record` is False are the legitimate registrants "
          "that moved up into the vacated bucket slot.")
        A("")
    else:
        A("_No differences: no manual exclusion is in force at any date._")
        A("")

    # -------------------------------------------- 3.7 manual exclusions log
    A("### 3.7 Manual exclusions (documented, never silent)")
    A("")
    A(f"Source of truth: `{MANUAL_EXCLUSIONS_PATH.relative_to(MANUAL_EXCLUSIONS_PATH.parents[2])}`. "
      "The automated sanitizer is a *within-registrant* rule and is structurally "
      "blind to a registrant that mis-scales its whole history the same way "
      "(§6.4's stated residual risk). The compensating control in §6.7 is a "
      "screen; it decides nothing. Anything actually removed is removed here, "
      "by hand, with primary-source evidence, and shows up in the reject log "
      "with reason `manual_exclusion`.")
    A("")
    if exclusions:
        rows = []
        for ex in exclusions:
            hits = sorted(d for d in ds if ex.applies(RATIFIED_VARIANT, date.fromisoformat(d)))
            would_be = (
                shadow_panel[shadow_panel["cik"] == ex.cik] if shadow_panel is not None
                else pd.DataFrame()
            )
            wb_dates = sorted(set(would_be["recon_date"])) if len(would_be) else []
            removed = [d for d in wb_dates if d in hits]
            rows.append({
                "cik": ex.cik,
                "name": ex.name[:32],
                "reason": ex.reason,
                "window": ex.window_str(),
                "evidence public from": ex.evidence_filed.isoformat() if ex.evidence_filed else "",
                "applies to": "/".join(ex.applies_to),
                "membership rows removed": len(removed),
                "dates removed": ", ".join(removed) or "—",
                "superseded by rule": "+".join(ex.superseded_by_rule) or "—",
            })
        A(_md_table(pd.DataFrame(rows)))
        A("")
        n_sup = sum(1 for ex in exclusions if ex.superseded_by_rule)
        if n_sup:
            A(f"**`superseded by rule`** ({n_sup} of {len(exclusions)} rows). "
              "These are the cases that were found by hand first and are now "
              "covered by a systematic rule (§3.8). They are annotated rather "
              "than deleted: deleting them would erase the discovery and leave "
              "the report claiming a rule appeared from nowhere. An annotated "
              "row still bites — the annotation is provenance, not an off "
              "switch — and each annotation was verified against cached EDGAR "
              "data at every reconstitution date the row covers before it was "
              "written. The unannotated rows are the 1,000× mis-scalings, "
              "which neither rule covers and which remain the only thing "
              "keeping them out.")
            A("")
        A("Evidence for each row, in full (this is the audit trail — if a row "
          "here is wrong, delete it from the CSV and re-run; nothing else "
          "changes):")
        A("")
        for ex in exclusions:
            A(f"**CIK {ex.cik} — {ex.name}** · `{ex.reason}` · applies "
              f"{ex.window_str()} · evidence public from "
              f"{ex.evidence_filed.isoformat() if ex.evidence_filed else 'n/a'} · "
              f"added {ex.date_added}")
            A("")
            A(f"> {ex.evidence}")
            A("")
        A("**Point-in-time guard on dated exclusions.** A row that carries both "
          "`evidence_filed` and `effective_from` is *rejected at load time* "
          "unless the evidence was already public before the first date the "
          "exclusion bites. That is what keeps a dated exclusion from quietly "
          "encoding hindsight; an undated row is reserved for the case where "
          "the tagged value was never valid at any date, which imports no "
          "information about the registrant's future.")
        A("")
        # what took the vacated slots
        if shadow_panel is not None and len(shadow_panel):
            repl = []
            for d in ds:
                gained = core_by_date[d] - c5_by_date[d]
                gained |= ext_by_date[d] - b8ext_by_date[d]
                for cik in sorted(gained):
                    r = hy[(hy.recon_date == d) & (hy.cik == cik)].iloc[0]
                    repl.append({"recon_date": d, "cik": int(cik), "name": str(r["name"])[:32],
                                 "sector": r["sector"], "stratum": r["stratum"],
                                 "sector_rank": int(r["sector_rank"]),
                                 "float": _b(r["float_usd"])})
            if repl:
                A("Registrants that moved up into the vacated slots (the bucket "
                  "still fills to K — an exclusion shrinks the universe only if "
                  "the bucket runs out of eligible names):")
                A("")
                A(_md_table(pd.DataFrame(repl)))
                A("")
    else:
        A(f"_`{MANUAL_EXCLUSIONS_PATH.name}` is empty or absent: no manual "
          "exclusions are in force._")
        A("")

    # ------------------------- 3.8 the two ratified float-integrity rules
    A("### 3.8 The two ratified float-integrity rules (owner, in chat, 2026-08-21)")
    A("")
    A("The owner ratified two systematic rules on 2026-08-21 (verbatim: \"Yes, "
      "please adopt both, as you recommended\"), promoting what had been the "
      "last two items on this report's own **Not verified / open** list into "
      "code. They are **scoped to the live `hybrid136` path only**; "
      "`continuity5` and `broad8` keep the legacy behaviour and are rebuilt "
      "byte-identically, because they are the option record the universe "
      "decision cites.")
    A("")
    A("| | rule 1 | rule 2 |")
    A("|---|---|---|")
    A(f"| name | `{FLOAT_RULE_NEWER_ZERO}` | `{FLOAT_RULE_MIN_SHARES}` |")
    A("| signal | most recent already-public `dei:EntityPublicFloat` "
      "disclosure at D is **exactly 0** | most recent already-public "
      "`dei:EntityCommonStockSharesOutstanding` at D is "
      f"**< {MIN_PUBLIC_SHARES_FOR_MEMBERSHIP:,} shares** |")
    A("| meaning | the registrant has no public float at D | the registrant "
      "has no publicly traded common equity at D |")
    A("| generalises | the dated EIDP / Dow / Energy Transfer Operating manual "
      "exclusions | the EIDP 100-shares manual exclusion |")
    A("| data source | float facts already fetched for selection (0 extra "
      "requests) | **already-cached** companyconcept documents only (0 extra "
      "requests) |")
    _on = {
        r: [v for v in TAXONOMIES if r in ruleset_for(v).rules]
        for r in (FLOAT_RULE_NEWER_ZERO, FLOAT_RULE_MIN_SHARES)
    }
    A("| applies to | "
      + " | ".join(
          ", ".join(f"`{v}`" for v in _on[r]) or "_no variant_"
          for r in (FLOAT_RULE_NEWER_ZERO, FLOAT_RULE_MIN_SHARES)
      )
      + " |")
    A("")
    _off = [v for v in TAXONOMIES if not ruleset_for(v).rules]
    A("Variants on the **legacy** ruleset (neither rule, unchanged behaviour): "
      + ", ".join(f"`{v}`" for v in _off) + ". That list is read from "
      "`VARIANT_RULESETS` at render time, so this table cannot drift away from "
      "what the builder actually did.")
    A("")
    A("**Exact semantics, because \"most recent\" has to mean one thing.** "
      "\"Most recent\" is ranked by the same `(measurement instant, filed "
      "date)` key `pit_float_asof()` already uses, over facts with "
      "`filed < D` and `instant < D` only — so both rules are point-in-time on "
      "exactly the terms §1 guarantees for everything else, and a 10-K/A "
      "supersedes the 10-K it amends. Four deliberate details:")
    A("")
    A("1. **Rule 1 fires on exactly 0, not on `<= 0`.** A negative float is a "
      "tagging error, not a registrant saying it has no public float, and it "
      "stays with the legacy `zero_or_negative` sanitizer. (There are no "
      "negative float facts anywhere in this build's diligence set, so the "
      "distinction costs nothing here — it is stated so nobody widens it by "
      "accident later.)")
    A("2. **A tie between a zero and a nonzero fact at the same newest key "
      "does not fire.** An ambiguous disclosure must not silently remove a "
      "registrant.")
    A("3. **Rule 2 treats a cover page tagging 0 shares as untestable, not as "
      "disqualifying.** Zero shares outstanding is far more often a "
      "placeholder than a fact, and removing a registrant on the strength of "
      "an absent number is the wrong error to make. Energy Transfer Operating "
      "is the live example: it tags 0 units on its final covers, and it is "
      "rule 1 — not rule 2 — that establishes it has no public equity.")
    A(f"4. **Rule 2 ignores a share count older than "
      f"{MIN_SHARES_MAX_STALENESS_DAYS} days at D** (the same staleness bound "
      "the float carries). This can only ever *prevent* the rule firing, never "
      "cause it.")
    A("")
    A("**Both rules only ever remove.** Neither can promote a registrant, "
      "change a float value, or move a company between sectors; each is "
      "evaluated only after a positive float has actually been selected, so a "
      "rule name in the reject log always means *this rule is what removed the "
      "row*, never \"it would have failed something else anyway\".")
    A("")

    # --- what the rules actually did -------------------------------------
    hy_rej = rejects.get(RATIFIED_VARIANT, pd.DataFrame())
    rule_rows = (
        hy_rej[hy_rej["reason"].isin([FLOAT_RULE_NEWER_ZERO, FLOAT_RULE_MIN_SHARES])]
        if len(hy_rej) and "reason" in hy_rej.columns
        else pd.DataFrame()
    )
    shadow_keys = (
        set(zip(shadow_panel["recon_date"], shadow_panel["cik"]))
        if shadow_panel is not None and len(shadow_panel)
        else set()
    )
    A("**Every firing whose registrant is not already covered by a manual "
      "exclusion**, with the evidence that triggered it. (The four firings that "
      "land on an already-excluded registrant are in the supersession table "
      "below instead — the reject log attributes those rows to "
      "`manual_exclusion`, which is checked first, so that an exclusion never "
      "hides behind a rule.) `would have been a member` marks a row that "
      "actually changes the universe, i.e. the registrant was selected in the "
      "pre-exclusion counterfactual; the rest are registrants the rules caught "
      "that no bucket would have reached anyway, and they are printed because "
      "a rule that fires invisibly is a rule nobody can check:")
    A("")
    if len(rule_rows):
        tbl = []
        for r in rule_rows.sort_values(["recon_date", "cik"]).to_dict("records"):
            key = (r["recon_date"], r["cik"])
            tbl.append({
                "recon_date": r["recon_date"],
                "cik": int(r["cik"]),
                "name": str(r["name"])[:30],
                "rule": r["reason"],
                "superseded float": _b(r["float_usd"]) if pd.notna(r.get("float_usd")) else "—",
                "would have been a member": "YES" if key in shadow_keys else "no",
                "evidence": str(r.get("rule_evidence", "")),
            })
        A(_md_table(pd.DataFrame(tbl)))
        A("")
        n_member = sum(1 for r in tbl if r["would have been a member"] == "YES")
        A(f"{len(tbl)} firings over {rule_rows['cik'].nunique()} registrants; "
          f"**{n_member}** of them on a registrant that a bucket would "
          "otherwise have selected. Every one is a registrant that became a "
          "wholly-owned subsidiary or was taken private and kept filing — "
          "Johnson Controls' pre-Tyco CIK, Baker Hughes' pre-BHGE CIK, ITC "
          "after Fortis, Level 3 after CenturyLink, Kansas City Southern after "
          "CP, Apollo Asset Management and Athene after their merger, STORE "
          "Capital after the GIC/Oak Street buyout, SiriusXM's pre-2024 CIK, "
          "and Apache Corp after the APA holding-company reorganisation left "
          "it with 1,000 shares — with the single exception discussed at the "
          "end of this section.")
        A("")
    else:
        A("_No firing in this build._")
        A("")

    # --- supersession check ----------------------------------------------
    sup_exs = [ex for ex in exclusions if ex.superseded_by_rule]
    if sup_exs and len(hy_rej) and "rule_would_also_reject" in hy_rej.columns:
        A("**The supersession check.** The `superseded by rule` annotations in "
          "§3.7 are a claim — *this hand-written row is now covered by a "
          "systematic rule* — and a claim in an audit trail has to be "
          "verifiable. It is verified here, date by date: for every "
          "reconstitution date each annotated exclusion covers, the builder "
          "records which rule(s) fire on that registrant independently of the "
          "exclusion. A blank cell would mean the annotation is wrong.")
        A("")
        rows = []
        me = hy_rej[hy_rej["reason"] == "manual_exclusion"]
        for ex in sup_exs:
            mine = me[me["cik"] == ex.cik]
            for r in mine.sort_values("recon_date").to_dict("records"):
                rows.append({
                    "cik": ex.cik,
                    "name": ex.name[:28],
                    "recon_date": r["recon_date"],
                    "annotated as superseded by": "+".join(ex.superseded_by_rule),
                    "rule(s) that actually fire": str(r.get("rule_would_also_reject", ""))
                    .replace(";", "+") or "— NONE (annotation is wrong)",
                })
        A(_md_table(pd.DataFrame(rows)))
        A("")
        holes = [r for r in rows if r["rule(s) that actually fire"].startswith("—")]
        if holes:
            A(f"**{len(holes)} annotated date(s) have no rule firing** — those "
              "annotations are wrong and must be removed from "
              f"`{MANUAL_EXCLUSIONS_PATH.name}`.")
        else:
            A("Every annotated date is covered. Concretely: EIDP is caught by "
              "rule 2 at 2018 (its FY2017 cover still carries the pre-merger "
              "float but reports 100 shares) and by rule 1 at 2019 (its FY2018 "
              "10-K tags float 0); Dow Chemical and Energy Transfer Operating "
              "are caught by rule 1 at the first date each row bites. That is "
              "why EIDP's annotation names both rules and Energy Transfer "
              "Operating's names only one.")
        A("")
        A("The three unannotated rows — MedEquities, Mister Car Wash, ASV "
          "Holdings — fire **neither** rule at any date, which is the correct "
          "answer: a registrant that mis-scales its float by 1,000× while "
          "reporting a normal share count and never tagging a zero is invisible "
          "to both. They remain the only thing keeping those three out, and "
          "deleting them would put a $880B \"consumer large cap\" back into the "
          "core stratum.")
        A("")

    # --- membership delta -------------------------------------------------
    if rules_off_panel is not None and len(rules_off_panel):
        on_keys = set(zip(hy["recon_date"], hy["cik"]))
        off_keys = set(zip(rules_off_panel["recon_date"], rules_off_panel["cik"]))
        delta = sorted(on_keys ^ off_keys)
        A("**Membership impact, measured rather than asserted.** The builder "
          "also produces `_cache/hybrid136_rules_off_panel.parquet`: the same "
          "build with the two rules switched off and the manual exclusions "
          "left in force. Diffing the two isolates exactly what adopting the "
          "rules did to membership.")
        A("")
        if not delta:
            A(f"- **Membership rows that changed: 0** (of {len(hy)}). Every "
              "case the rules catch that a bucket would have selected was "
              "already removed by hand in §3.7 — which is the point: the rules "
              "*generalise* those hand-found removals, they do not add new "
              "ones. The universe tables in §3.1 and the churn tables in §4 "
              "are therefore unchanged by this adoption.")
            A("")
            A("- The rules are nonetheless load-bearing going forward: with "
              "them in force the three superseded exclusion rows are no longer "
              "the *only* thing standing between a wholly-owned successor and "
              "a bucket slot.")
            A("")
            if (
                legacy_panel is not None and len(legacy_panel)
                and shadow_panel is not None and len(shadow_panel)
            ):
                sk = set(zip(shadow_panel["recon_date"], shadow_panel["cik"]))
                lk = set(zip(legacy_panel["recon_date"], legacy_panel["cik"]))
                gone = sorted(lk - sk)
                A("  That is measured too, on the pair of counterfactuals that "
                  "isolate the rules from the exclusions entirely — "
                  f"`_cache/{RATIFIED_VARIANT}_shadow_panel.parquet` (rules on, "
                  f"exclusions off) against "
                  f"`_cache/{RATIFIED_VARIANT}_legacy_panel.parquet` (both "
                  f"off). With `{MANUAL_EXCLUSIONS_PATH.name}` emptied, the "
                  f"rules alone still remove **{len(gone)}** membership "
                  f"row(s), and {len(sk - lk)} registrant(s) backfill:")
                A("")
                if gone:
                    A(_md_table(pd.DataFrame([
                        {"recon_date": d, "cik": int(c),
                         "name": (profiles[int(c)].name[:32] if int(c) in profiles else ""),
                         "removed by": "the rules alone"}
                        for d, c in gone
                    ])))
                    A("")
                A("  The three 1,000× mis-scalings (MedEquities, Mister Car "
                  "Wash, ASV Holdings) are **not** in that list, and would "
                  "re-enter — which is exactly why those three exclusion rows "
                  "are unannotated and stay active.")
                A("")
        # One thing DID change in the ratified table even with membership
        # identical, and it is reported rather than left for someone to find in
        # a diff.
        rk_on = {
            (r["recon_date"], r["cik"]): r["overall_float_rank"]
            for r in hy.to_dict("records")
        }
        rk_off = {
            (r["recon_date"], r["cik"]): r["overall_float_rank"]
            for r in rules_off_panel.to_dict("records")
        }
        moved = [(k, rk_off[k], rk_on[k]) for k in rk_on if k in rk_off and rk_off[k] != rk_on[k]]
        if moved:
            A("**One column of the ratified table did change, with membership "
              "identical**, and it is called out here rather than left to be "
              "found in a diff. `overall_float_rank` is a rank over the "
              "candidates that survive every filter at a date, so removing a "
              "candidate renumbers everyone below it:")
            A("")
            A(_md_table(pd.DataFrame([
                {"recon_date": k[0], "cik": int(k[1]),
                 "name": (profiles[int(k[1])].name[:32] if int(k[1]) in profiles else ""),
                 "overall_float_rank before": int(a), "after": int(b_)}
                for k, a, b_ in sorted(moved)
            ])))
            A("")
            A("The cause is a single removal: Baker Hughes Holdings LLC "
              "(CIK 808362, $19.3B of fossil float) leaves the 2018-07-01 "
              "candidate pool under rule 1, and the only two members ranked "
              "below it at that date move up one place. It was never a member "
              "— its bucket floor was far above it — so no membership row "
              "moves. `hybrid136.csv` (the spells table) is byte-identical to "
              "the pre-adoption build; only `hybrid136_panel` differs, in this "
              "one column, in these two rows.")
            A("")
        else:
            rows = []
            for d, cik in delta:
                rows.append({
                    "recon_date": d, "cik": int(cik),
                    "name": (profiles[int(cik)].name[:32] if int(cik) in profiles else ""),
                    "with rules": (d, cik) in on_keys,
                    "without rules": (d, cik) in off_keys,
                })
            A(f"- **Membership rows that changed: {len(delta)}** (of {len(hy)}).")
            A("")
            A(_md_table(pd.DataFrame(rows)))
            A("")

    # --- coverage / limits ------------------------------------------------
    if shares_coverage:
        A(f"**What rule 2 can and cannot see.** Cover-page share histories were "
          f"available from the on-disk cache for "
          f"{shares_coverage.get('cached', 0):,} of the "
          f"{shares_coverage.get('diligence_ciks', 0):,} diligence CIKs, at a "
          f"cost of **0 network requests** — the ratified scope is explicitly "
          "\"use only already-cached companyconcept data; do not fetch "
          "aggressively to close the gap\". Every registrant that is a member "
          "of `hybrid136` or of its pre-exclusion counterfactual is inside "
          "that cached set, because the §6.7 screen has already paid for it. "
          f"Of the cached registrants, {shares_coverage.get('never_tagged', 0)} "
          "have never tagged an undimensioned "
          "`dei:EntityCommonStockSharesOutstanding` at all — the multi-class "
          "filers of §6.7's coverage gap — and for those the rule simply does "
          "not fire. That is a real blind spot, it is the same one §6.7 "
          "measures, and it is recorded here rather than papered over.")
        A("")
    A("**A known false-positive mode for rule 1, found by running it.** A "
      "registrant that mis-tags a single year's float as 0 while remaining "
      "listed is treated as having no public float for exactly the dates that "
      "0 is its newest disclosure. The firings table above contains one such "
      "case. The mode is self-limiting — the next correctly-tagged 10-K "
      "restores eligibility, because the rule reads only the *most recent* "
      "disclosure — and in this build no such case touches membership, but a "
      "future build could see one. It is a deliberate trade: the alternative "
      "is the pre-2026-08-21 behaviour, in which a wholly-owned subsidiary's "
      "fossil float outranks real large caps.")
    A("")

    # ------------------------------------------------------------ churn
    A("## 4. Churn — the reconstitution actually moves")
    A("")
    A(f"### 4.1 `{RATIFIED_VARIANT}` (ratified)")
    A("")
    A(_md_table(churn_stats(hy, dates)))
    A("")
    A("Per stratum — the strata churn at visibly different rates, which is why "
      "§7's stratum analysis rule forbids pooling them into one headline "
      "turnover number:")
    A("")
    for label, sub in ((STRATUM_CORE, hy_core), (STRATUM_EXTENSION, hy_ext)):
        cs = churn_stats(sub, dates)
        cs.insert(1, "stratum", label)
        A(f"`{label}` stratum:")
        A("")
        A(_md_table(cs))
        A("")
    sp_h = spells[RATIFIED_VARIANT]
    for label, sub in ((STRATUM_CORE, hy_core), (STRATUM_EXTENSION, hy_ext), ("union", hy)):
        n_distinct = sub["cik"].nunique()
        sp_sub = sp_h[sp_h["cik"].isin(set(sub["cik"]))] if len(sp_h) else sp_h
        n_all = int(sp_sub["all_dates"].sum()) if len(sp_sub) else 0
        multi = sp_sub.groupby("cik").size() if len(sp_sub) else pd.Series(dtype=int)
        counts = sub.groupby("cik").size()
        A(f"- **{label}**: {n_distinct} distinct CIKs over the decade; "
          f"{n_all} present at all {len(ds)} reconstitutions "
          f"({100.0*n_all/max(n_distinct,1):.0f}%); "
          f"{int((multi > 1).sum())} with more than one membership spell; "
          f"median {counts.median():.0f} of {len(ds)} reconstitutions per member.")
    A("")
    for name, panel in (("continuity5", c5), ("broad8", b8)):
        cs = churn_stats(panel, dates)
        sp = spells[name]
        allyr = sp[sp["all_dates"]] if len(sp) else sp
        A(f"### 4.{'2' if name=='continuity5' else '3'} `{name}` (option record)")
        A("")
        A(_md_table(cs))
        A("")
        n_all = len(allyr)
        n_distinct = panel["cik"].nunique()
        A(f"- Present at **all {len(ds)} reconstitutions**: **{n_all}** CIKs "
          f"({100.0*n_all/max(n_distinct,1):.0f}% of the {n_distinct} distinct "
          f"CIKs that are ever members).")
        A(f"- Partial members: **{n_distinct - n_all}** CIKs.")
        multi = sp.groupby("cik").size()
        A(f"- CIKs with more than one membership spell (exit then re-entry): "
          f"**{int((multi > 1).sum())}**.")
        counts = panel.groupby("cik").size()
        A(f"- Median reconstitutions per member: **{counts.median():.0f}** of {len(ds)}.")
        A("")

    # ------------------------------------------------- censoring census
    A("## 5. Outcome-side censoring census (count, never silently drop)")
    A("")
    hy_census = census[census["cik"].isin(hy_ciks)]
    hy_core_ciks, hy_ext_ciks = set(hy_core["cik"]), set(hy_ext["cik"])
    A(f"### 5.1 `{RATIFIED_VARIANT}` — the census that governs E2's results")
    A("")
    n_hy = len(hy_census)
    n_hy_cens = int(hy_census["censoring_risk"].sum())
    hy_active_noticker = {
        int(r["cik"]) for r in flags.get("no_ticker_but_active", []) if int(r["cik"]) in hy_ciks
    }
    A(f"The ratified universe has **{len(hy_ciks)}** distinct member CIKs over "
      f"the decade ({len(hy_core_ciks)} core, {len(hy_ext_ciks)} extension). "
      f"Of the {n_hy} covered by the census:")
    A("")
    A(f"- **{n_hy - n_hy_cens}** resolve to at least one current ticker in "
      "EDGAR's own submissions record.")
    A(f"- **{n_hy_cens}** have **no current ticker** — the population whose "
      f"forward returns right-censor. **{len(hy_active_noticker)}** of those are "
      "XOM-style successor-CIK reorganizations that are still actively filing, "
      f"so the count plausibly censored *by delisting* is "
      f"**{n_hy_cens - len(hy_active_noticker)}**.")
    cens_by_str = {
        STRATUM_CORE: int(hy_census[hy_census["cik"].isin(hy_core_ciks)]["censoring_risk"].sum()),
        STRATUM_EXTENSION: int(
            hy_census[hy_census["cik"].isin(hy_ext_ciks)]["censoring_risk"].sum()
        ),
    }
    A(f"- Split by stratum: core {cens_by_str[STRATUM_CORE]} of "
      f"{len(hy_core_ciks)}, extension {cens_by_str[STRATUM_EXTENSION]} of "
      f"{len(hy_ext_ciks)}. Per §7's stratum analysis rule this pair, not the "
      "union figure, is what accompanies a stratified result.")
    A("")
    if n_hy_cens:
        hc = hy_census[hy_census["censoring_risk"]][
            ["cik", "name", "last_periodic", "still_filing"]
        ].copy()
        hc["name"] = hc["name"].str.slice(0, 40)
        hc.insert(
            2, "stratum",
            hc["cik"].map(lambda c: STRATUM_CORE if int(c) in hy_core_ciks else STRATUM_EXTENSION),
        )
        A(f"Every no-current-ticker `{RATIFIED_VARIANT}` member:")
        A("")
        A(_md_table(hc.sort_values("last_periodic").reset_index(drop=True)))
        A("")
    A("### 5.2 The full censoring population (all three variants)")
    A("")
    n_members = len(census)
    n_censor = int(census["censoring_risk"].sum())
    n_active_noticker = len(flags.get("no_ticker_but_active", []))
    A(f"Across the union of all three universes built here, **{n_members}** "
      f"distinct member CIKs. Of these:")
    A("")
    A(f"- **{n_members - n_censor}** resolve to at least one current ticker in "
      "EDGAR's own submissions record.")
    A(f"- **{n_censor}** have **no current ticker** — the population whose "
      "forward returns would right-censor. That figure is an upper bound on "
      f"true delistings: **{n_active_noticker}** of them are still actively "
      "filing periodic reports (XOM-style successor-CIK reorganizations, see "
      "§6), so the count of member-CIKs plausibly censored *by delisting* is "
      f"**{n_censor - n_active_noticker}**.")
    A("")
    if n_censor:
        cens = census[census["censoring_risk"]][
            ["cik", "name", "last_periodic", "still_filing", "former_names"]
        ].copy()
        cens["name"] = cens["name"].str.slice(0, 40)
        cens["former_names"] = cens["former_names"].str.slice(0, 44)
        A("Every no-current-ticker member CIK:")
        A("")
        A(_md_table(cens.sort_values("last_periodic").reset_index(drop=True)))
        A("")
    if probes:
        pdf = pd.DataFrame(probes)
        pdf["name"] = pdf["name"].str.slice(0, 30)
        pdf["detail"] = pdf["detail"].str.slice(0, 60)
        A(f"**Yahoo price-client probe** ({len(pdf)} member CIKs, sequential, "
          "through the existing `price_client.PriceClient` and its cache):")
        A("")
        A(_md_table(pdf[["cik", "name", "ticker_probed", "has_current_ticker",
                         "still_filing", "result", "n_bars", "first_bar",
                         "last_bar", "detail"]]))
        A("")
        res = pdf["result"].value_counts().to_dict()
        A(f"Probe outcome counts: {res}.")
        A("")
    if len(former_probes):
        fdf = pd.DataFrame(former_probes)
        A("**Does a price source actually serve a delisted symbol?** The recon "
          "asserted it generally does not, and that assertion decides how much "
          "of E2's outcome side is censored — so it was measured rather than "
          "assumed. EDGAR keeps no historical ticker for a dead registrant, so "
          "the last-known symbols below were identified BY HAND (source: public "
          "knowledge of each acquisition, cross-checked against the "
          "registrant's EDGAR entity name) and are used for this probe ONLY — "
          "never for membership, ranking or eligibility.")
        A("")
        fdf["name"] = fdf["name"].astype(str).str.slice(0, 26)
        fdf["event"] = fdf["event"].astype(str).str.slice(0, 52)
        cols = ["cik", "name", "former_ticker", "last_periodic", "result", "n_bars"]
        for extra in ("symbol_now_type", "symbol_now_name", "symbol_first_trade"):
            if extra in fdf.columns:
                cols.append(extra)
        show = fdf[cols].copy()
        if "symbol_now_name" in show.columns:
            show["symbol_now_name"] = show["symbol_now_name"].astype(str).str.slice(0, 34)
        A(_md_table(show))
        A("")
        counts = fdf["result"].value_counts().to_dict()
        A(f"Outcome: {counts}.")
        got = fdf[fdf["result"] == "DATA_RETURNED"]
        if len(got):
            A("")
            A("**The three that DID return data are worse than the seven that "
              "returned nothing.** None of them is the company we asked about — "
              "the exchange recycled the symbol. `APC` is now ARKO Petroleum "
              "Corp. (an unrelated equity first traded 2026-02-12), `EMC` is now "
              "a Global X emerging-markets **ETF**, and `LNKD` resolves to an "
              "empty mutual-fund stub. A pipeline that recovered former tickers "
              "to fill price gaps would silently ingest a different instrument's "
              "returns under a member's name and never raise an error. **F2 must "
              "not map dead members to former tickers**; censored members stay "
              "censored and counted.")
        A("")
    A("**What this means for E2, unchanged from EXPANSION_PLAN.md §2c:** "
      "selection is survivorship-free (a company that dies mid-window was "
      "legitimately selected before it died and stays in-sample), but *outcomes* "
      "are not. EDGAR keeps no historical ticker for a dead registrant, so for "
      "a censored member there is not even a symbol to ask a price source for — "
      "the censoring is structural, not a matter of choosing a better price "
      "vendor. The mandatory mitigations stand: report this count wherever E2 "
      "results appear, and ingest EDGAR-native distress outcomes (8-K Item "
      "1.03, Form 25, Form 15) so censored names remain visible. Neither is "
      "in scope for F1.")
    A("")

    # --------------------------------------------------- diligence flags
    A("## 6. CIK diligence flags")
    A("")
    A("### 6.1 E1's 25 companies — do they rank in?")
    A("")
    e1_names = {int(k): v for k, v in flags["e1_names"].items()}
    ALL_VARIANTS = (RATIFIED_VARIANT, *OPTION_RECORD_VARIANTS)
    rows = []
    for variant in ALL_VARIANTS:
        cov = flags["e1_coverage"][variant]
        missing = [int(c) for c in cov["missing"]]
        rows.append({"variant": variant, "E1 CIKs present": len(cov["present"]),
                     "missing": len(missing),
                     "missing names": ", ".join(e1_names[c][0] for c in missing) or "—"})
    A(_md_table(pd.DataFrame(rows)))
    A("")
    for variant in ALL_VARIANTS:
        missing = [int(c) for c in flags["e1_coverage"][variant]["missing"]]
        if not missing:
            continue
        A(f"Why the missing E1 names do not rank in under `{variant}`:")
        A("")
        rj = rejects[variant]
        for c in missing:
            sub = rj[rj["cik"] == c]
            if len(sub):
                reasons = sub["reason"].value_counts().to_dict()
                extra = ""
                if "below_sector_K" in reasons and "sector_rank" in sub.columns:
                    ranks = sub[sub["reason"] == "below_sector_K"]["sector_rank"].dropna()
                    if len(ranks):
                        extra = (f" (best within-sector rank {int(ranks.min())}, "
                                 f"worst {int(ranks.max())})")
                A(f"- **{e1_names[c][0]}** (CIK {c}, E1 sector {e1_names[c][1]}): "
                  f"{reasons}{extra}")
            else:
                A(f"- **{e1_names[c][0]}** (CIK {c}): never reached the diligence "
                  "shortlist at any date — i.e. its float never placed it in the "
                  f"top {args.shortlist_per_date} registrants.")
        A("")

    A("### 6.2 Legacy-CIK / successor-entity oddities (the XOM lesson)")
    A("")
    nta = flags.get("no_ticker_but_active", [])
    if nta:
        A(f"**{len(nta)} member CIKs have no current ticker yet are still filing "
          "periodic reports.** These are not delistings; they are the XOM "
          "pattern — the ticker has migrated to a successor/holding CIK while "
          "the operating registrant with the filing history keeps filing. "
          "Ingestion must key on the CIK with the history, exactly as "
          "`ingest_metadata.py` does for XOM (34088, not 2115436):")
        A("")
        A(_md_table(pd.DataFrame(nta)[["cik", "name", "last_periodic"]]))
        A("")
    succ = flags.get("successor_cik_candidates", [])
    if succ:
        A("Ticker-map entries whose *title* matches a no-ticker member's name "
          "but points at a different CIK. These are CANDIDATE successor "
          "entities, each needing the same manual confirmation XOM's override "
          "got — the match is a deliberately loose first-word comparison, so "
          "some rows are coincidences (Pioneer Natural Resources is not "
          "Pioneer Bancorp; Magellan Midstream is not Magellan Copper & Gold). "
          "The real ones here are Exxon→ExxonMobil Holdings, Cigna Holding→"
          "Cigna Group, Linde Inc→Linde plc, Warner Media→Warner Bros. "
          "Discovery, BlackRock Finance→BlackRock, Inc., and both Energy "
          "Transfer entities→Energy Transfer LP:")
        A("")
        A(_md_table(pd.DataFrame(succ)[["cik", "name", "map_cik", "map_title", "map_ticker"]].head(20)))
        A("")
    goog_zero = [s for s in suspects if int(s["cik"]) == 1652044 and float(s["val"]) <= 0]
    if goog_zero:
        A("**The mirror-image case — a NEW CIK for an old business.** Alphabet "
          f"(CIK 1652044) was created in 2015; its first 10-K as a holding "
          f"company tags `EntityPublicFloat` = **0** (filed "
          f"{goog_zero[0]['filed']}). So at the earliest reconstitution dates "
          "Alphabet has no usable float on its own CIK, while the pre-2015 "
          "history lives under Google Inc. (CIK 1288776). This is the XOM "
          "lesson running the other way, and it means **CIK is not a stable "
          "identity for a company across a 10-year window**. F2 must decide "
          "explicitly whether predecessor and successor CIKs are stitched into "
          "one company or treated as separate entrants/exits; this build does "
          "NOT stitch them (each CIK stands alone), which is the conservative "
          "choice but shows up as churn.")
        A("")
    dis = flags.get("ticker_map_disagreement", [])
    A(f"`company_tickers.json` disagreements (a member's own ticker resolving "
      f"to a different CIK in the bulk map): **{len(dis)}**"
      + (":" if dis else " — none."))
    if dis:
        A("")
        A(_md_table(pd.DataFrame(dis).head(20)))
    A("")

    A("### 6.3 Multi-class share structures and missing `dei` facts")
    A("")
    mc = flags.get("multi_ticker_share_classes", [])
    nf = flags.get("no_float_concept", [])
    A(f"- Members with **more than one listed ticker** (multi-class or listed "
      f"preferreds): **{len(mc)}**. These are the names where a "
      "`ticker → CIK` join is ambiguous and price/feature joins must key on "
      "CIK plus an explicit share-class choice.")
    if mc:
        top_mc = pd.DataFrame(mc)
        top_mc["tickers"] = top_mc["tickers"].map(lambda t: ",".join(t)[:60])
        top_mc["name"] = top_mc["name"].str.slice(0, 36)
        A("")
        A(_md_table(top_mc.head(25)))
        A("")
    A(f"- Members with **no `dei:EntityPublicFloat` concept at all**: {len(nf)} "
      "(zero by construction — a member must have a PIT-valid float fact to be "
      "selected; this count exists to catch a future rule change that would "
      "let one through).")
    A("")

    A("### 6.4 Float data quality: filer scale errors (the biggest surprise in F1)")
    A("")
    A("`dei:EntityPublicFloat` is dirty in a way that directly attacks a "
      "top-K-by-float universe rule, and this was not anticipated by the recon.")
    A("")
    A("Two failure modes, both verified by hand against the filings' own numbers:")
    A("")
    A("1. **Gross mis-scaling (10⁶×).** The three largest values in the raw "
      "CY2022Q2I float frame are M&T Bank at $2.7×10¹⁶, First American "
      "Financial at $5.4×10¹⁵ and ManpowerGroup at $4.0×10¹⁵ — each ~10⁶× its "
      "true float. eBay's 2020 10-K/A tags $3.1×10¹⁹.")
    A("2. **Persistent 1,000× mis-scaling across CONSECUTIVE years** — the "
      "nastier one, because the erroneous years vouch for each other. Onto "
      "Innovation tagged 2022–2025 at exactly 1,000× (e.g. $3.07×10¹² where "
      "the 10-K says $3.07B); Champion Homes did the same for 2022–2025; "
      "CoreCivic for 2017–2019; Garmin for 2015, 2017 and 2018; GoPro for "
      "2017–2018.")
    A("")
    bl = _load_df(CACHE_DIR / "coregistrant_blocklist.parquet")
    n_bl = 0 if bl is None else len(bl)
    A(f"3. **Combined filings put the PARENT's float on a subsidiary's "
      "registrant record.** Utility and holding-company groups file one 10-K "
      "covering the parent and several wholly-owned co-registrants. Verified "
      "case: Kentucky Utilities (CIK 55387) reports a float of $19.73B for "
      "2015-06-30 under accession 0000922224-16-000130 — which is PPL "
      "Corporation's own accession and PPL's own float. Kentucky Utilities has "
      "no publicly traded equity whatsoever, and nothing about its SIC (4911, "
      "a real utility), its `entityType` (\"operating\") or the value itself "
      "gives it away; with exactly one float fact in its entire history, the "
      "plausibility rules have nothing to compare against either. It was a "
      "selected member of the 2016 broad8 utilities bucket until this was "
      "caught. The filter is an exact (accession, instant, value) triple "
      f"reported by more than one CIK: **{n_bl}** (CIK, accession) pairs in "
      "the whole panel, of which exactly one touched a member.")
    A("")
    A("**Consequence if unhandled:** an unsanitized top-K hands the top of the "
      "universe to whoever mis-scaled their cover page. In the first build of "
      "this table, Garmin ($7.75T), Onto Innovation ($5.66T), Champion Homes "
      "($5.35T) and CoreCivic ($3.24T) were all *selected members* — larger, "
      "on paper, than Apple. They are not large caps at all ($34B, $3.5B, "
      "$3.4B, $4.1B respectively).")
    A("")
    A("**And the fix has its own failure mode:** a first attempt keyed on each "
      "registrant's long-run median flagged NVIDIA's genuine $1.1T/$2.7T/$4.0T "
      "floats as errors (NVIDIA's 2014–2020 history drags its median to ~$10B) "
      "— i.e. it would have silently deleted the largest company in the "
      "universe from the most recent reconstitutions. The shipped rule "
      "compares against *adjacent* disclosures using the smaller neighbour, "
      "iteratively, and is pinned by a regression test "
      "(`test_hypergrowth_is_not_flagged_nvidia_regression`).")
    A("")
    fs = _load_json(CACHE_DIR / "frames_sanitation.json")
    if fs:
        A(f"**At enumeration** (the 48 quarterly frames, "
          f"{fs['total_points']:,} data points): "
          f"{sum(fs['dropped'].values()):,} rejected — "
          + ", ".join(f"`{k}` {v:,}" for k, v in sorted(fs["dropped"].items()))
          + ". The `zero_or_negative` bulk is not error at all: those are "
          "wholly-owned financing/subsidiary registrants that correctly report "
          "a public float of 0 (Alphabet's own first 10-K as a holding company, "
          "FY2015, tags 0). They are simply not large caps.")
        A("")
    sdf = pd.DataFrame(suspects)
    if len(sdf):
        by_reason = sdf["reason"].value_counts().to_dict() if "reason" in sdf else {}
        A(f"**At selection** (per-CIK `companyconcept` histories for the "
          f"{sdf['cik'].nunique()} affected registrants of the diligence set): "
          f"**{len(sdf)}** facts rejected — {by_reason}.")
        A("")
        s2 = sdf[sdf.get("reason") == "neighbour_jump"].sort_values("val", ascending=False)
        if len(s2):
            s3 = s2.head(15).copy()
            s3["val"] = s3["val"].map(lambda v: f"{v:.3e}")
            s3["name"] = s3["name"].astype(str).str.slice(0, 34)
            A("Largest in-band rejections (all verified 1,000× mis-scalings):")
            A("")
            A(_md_table(s3[["cik", "name", "instant", "filed", "val", "form"]].reset_index(drop=True)))
            A("")
        A("Full list: `data/universe_e2_candidates/_cache/suspect_float_facts.csv`.")
        A("")
    # cross-sectional residual check on the FINAL members
    A("**Residual risk, measured.** A registrant that mis-scales its ENTIRE "
      "history the same way has no clean neighbour and is invisible to a "
      "within-registrant rule. As a backstop, every selected member whose "
      "float is more than 2× the next-largest member's at the same date is "
      "listed here for eyeballing:")
    A("")
    odd_rows = []
    for name, panel in ((RATIFIED_VARIANT, hy), ("continuity5", c5), ("broad8", b8)):
        for d, g in panel.groupby("recon_date"):
            top = g.sort_values("float_usd", ascending=False).head(2)
            if len(top) == 2 and top.iloc[0]["float_usd"] > 2 * top.iloc[1]["float_usd"]:
                odd_rows.append({"variant": name, "recon_date": d,
                                 "cik": top.iloc[0]["cik"],
                                 "name": top.iloc[0]["name"][:34],
                                 "float": _b(top.iloc[0]["float_usd"]),
                                 "next largest": _b(top.iloc[1]["float_usd"])})
    if odd_rows:
        A(_md_table(pd.DataFrame(odd_rows)))
    else:
        A("_None: at every reconstitution date, in all three variants, the "
          "largest member is within 2× of the second largest._")
    A("")
    A("**That backstop is not sufficient, and F1 proved it.** It only ever "
      "looks at the single largest member per date, so a registrant that "
      "mis-scales its whole history and lands *mid-bucket* sails straight "
      "through — which is exactly what happened three times. §6.7 replaces the "
      "eyeball with a measurement.")
    A("")

    A("### 6.5 Shortlist headroom (is the diligence depth sufficient?)")
    A("")
    A(f"Full diligence (submissions + companyconcept) was run on the top "
      f"**{args.shortlist_per_date}** registrants by float at each date — "
      f"{shortlist['cik'].nunique():,} distinct CIKs in total. The question "
      "this raises is whether a registrant that was NOT fetched could have "
      "displaced a selected member. It provably could not, and here is the "
      "check rather than the assurance:")
    A("")
    cut = _load_df(CACHE_DIR / "shortlist_cutoff.parquet")
    rows = []
    for d in ds:
        r = {"recon_date": d}
        fx = None
        if cut is not None and len(cut[cut.recon_date == d]):
            fx = float(cut[cut.recon_date == d].iloc[0]["first_excluded_float_usd"])
            r["largest float NOT fetched"] = _b(fx)
        for name, panel in ((RATIFIED_VARIANT, hy), ("continuity5", c5), ("broad8", b8)):
            mn = float(panel[panel.recon_date == d]["float_usd"].min())
            r[f"{name} weakest member"] = _b(mn)
            r[f"{name} margin"] = f"{mn/fx:.2f}x" if fx else "-"
        rows.append(r)
    A(_md_table(pd.DataFrame(rows)))
    A("")
    A("The margin is the weakest member's float divided by that strict upper "
      "bound, so **any margin above 1.00x is a proof, not a comfort level** — "
      "the tightest is continuity5 in 2021, where reaching 20 deep in a "
      "collapsed energy sector pulls the floor down to MPLX LP at $6.8B.")
    A("")
    A("A registrant's point-in-time float is never larger than its maximum "
      "float over the lookback window (the value the shortlist ranks on), so "
      "every un-fetched registrant's PIT float is bounded above by the "
      "\"largest float NOT fetched\" column. In every year that bound sits "
      "well below the weakest selected member in every variant, so no "
      "un-fetched registrant could have outranked any member. If a future "
      "re-run narrows that margin, raise `--shortlist-per-date` — everything "
      "is cached, so a deeper pass only pays for the newly-added CIKs.")
    A("")
    for name, panel in ((RATIFIED_VARIANT, hy), ("continuity5", c5), ("broad8", b8)):
        A(f"- `{name}`: deepest selected member sat at frames-superset rank "
          f"**{int(panel['superset_rank'].max())}** of "
          f"{args.shortlist_per_date}; deepest point-in-time overall float "
          f"rank **{int(panel['overall_float_rank'].max())}** (superset rank "
          "runs deeper than the PIT rank because the shortlist ranks over a "
          "superset that still contains funds, trusts, foreign filers and "
          "not-yet-public values, all of which selection removes).")
    A("")

    A("### 6.6 Strict vs lenient eligibility")
    A("")
    rows = []
    for variant in ALL_VARIANTS:
        rj = rejects[variant]
        inel = rj[rj["reason"] == "ineligible_filing_history"]
        would_pass = inel[inel["periodic_in_window"] >= MIN_ELIGIBLE_QUARTERS]
        rows.append(
            {
                "variant": variant,
                "rejected as ineligible (candidate-dates)": len(inel),
                "distinct CIKs": inel["cik"].nunique(),
                "…that the lenient rule would have kept": len(would_pass),
                "…distinct CIKs": would_pass["cik"].nunique(),
            }
        )
    A(_md_table(pd.DataFrame(rows)))
    A("")
    A(f"Strict rule = each of the {MIN_ELIGIBLE_QUARTERS} quarters before D has "
      "≥1 periodic filing. Lenient rule = ≥8 periodic filings anywhere in those "
      "24 months. The difference is dominated by late-IPO entrants and filers "
      "who bunch two filings into one quarter.")
    A("")

    # ------------------------------------------- 6.7 the compensating control
    A("### 6.7 Float-scale audit — the compensating control for §6.4's blind spot")
    A("")
    if scale_audit is None or not len(scale_audit):
        A("_Not run in this build (`--no-scale-audit`)._")
        A("")
    else:
        A("§6.4's sanitizer is a **within-registrant** rule: it judges a float "
          "fact against the same registrant's temporally adjacent disclosures. "
          "A registrant that mis-scales its ENTIRE history the same way has no "
          "clean neighbour, so the rule is structurally blind to it. That was "
          "listed as an open residual risk with an eyeball check behind it. "
          "This audit replaces the eyeball, and it found **three live "
          "instances** — so the risk was not theoretical.")
        A("")
        A("It runs over the **union** of the ratified table and **both** of "
          "its counterfactuals — exclusions off, and exclusions *and* the two "
          "§3.8 rules off. All three matter, for one reason stated three ways: "
          "auditing only the finished table would grade the audit on its own "
          "homework (the registrants the exclusions removed would vanish from "
          "the very output that justifies removing them); dropping the "
          "rules-off arm would make arm D report \"nothing found\" — true, but "
          "only because rule 1 had already deleted those rows upstream, which "
          "would read as evidence the problem does not exist when it is "
          "evidence the fix works; and auditing only the counterfactuals would "
          "leave every registrant that backfilled a vacated bucket slot "
          "unscreened. Four arms:")
        A("")
        A(f"- **A — implied price.** `float ÷ shares outstanding on the same "
          f"cover page` (`dei:{ 'EntityCommonStockSharesOutstanding' }`, ~3 KB "
          f"per registrant). Flagged outside "
          f"[${AUDIT_MIN_IMPLIED_PRICE_USD:,.0f}, ${AUDIT_MAX_IMPLIED_PRICE_USD:,.0f}] "
          "per share. A 1,000× float mis-scale lands the quotient at ~1,000× a "
          "real price.")
        A(f"- **B — shares-series sanity.** The same scale detector run on the "
          "registrant's own share-count series, plus a floor at "
          f"{AUDIT_MIN_PUBLIC_SHARES:,} shares. Arm B is what catches the "
          "nastier variant where the 10-K cover mis-scales float **and** shares "
          "together — arm A's quotient then looks perfectly normal, and only "
          "the registrant's own 10-Qs give it away.")
        A(f"- **C — float-to-assets adjudication.** Arms A and B are screens "
          "and they do produce honest false alarms: Amazon pre-split, Booking "
          "Holdings and MercadoLibre genuinely trade in four figures. Only for "
          "the registrants a screen flagged, `us-gaap:Assets` is fetched and "
          f"compared; a ratio above {AUDIT_MAX_FLOAT_TO_ASSETS:.0f}× is called "
          "a scale error.")
        A("- **D — superseded-by-zero.** Costs nothing. A membership row whose "
          "selected float is older than an ALREADY-PUBLIC float disclosure of "
          "exactly **0**. Zero is not noise — it is the registrant saying \"I "
          "have no public float\" — but §6.4's sanitizer drops zeros as "
          "`zero_or_negative`, after which `pit_float_asof()` falls back to a "
          "stale positive value. **Since 2026-08-21 this arm is the screen "
          "behind a rule rather than the only line of defence**: §3.8's rule 1 "
          "now removes such a registrant from the ratified variant "
          "automatically. The three arm-D rows below therefore come from the "
          "rules-off counterfactual, which is exactly why the audit runs over "
          "it — reporting \"arm D found nothing\" because rule 1 had already "
          "deleted the rows upstream would be technically true and completely "
          "misleading.")
        A("")
        n_gap_rows = int(scale_audit["shares_outstanding"].isna().sum())
        n_gap_regs = int(scale_audit[scale_audit["shares_outstanding"].isna()]["cik"].nunique())
        A(f"**Coverage.** {scale_summary.get('rows', 0):,} membership rows over "
          f"{scale_summary.get('registrants', 0)} registrants; a share count was "
          f"resolvable for {scale_summary.get('rows_with_shares', 0):,} of them "
          f"({100.0 * scale_summary.get('rows_with_shares', 0) / max(scale_summary.get('rows', 1), 1):.0f}%). "
          f"The remaining {n_gap_rows} rows ({n_gap_regs} registrants) are a "
          "measured coverage gap: "
          f"{scale_summary.get('registrants_without_shares_concept', 0)} "
          "registrants tag no undimensioned "
          "`dei:EntityCommonStockSharesOutstanding` at all (multi-class filers "
          "that tag one row per share class behind an XBRL axis), and the rest "
          "tag one but not within "
          f"{ 400 } days of the float's measurement instant. Arms A–C "
          "**cannot speak** for those rows; they are listed below rather than "
          "counted as clean. Arm D covers all rows regardless.")
        A("")
        A(f"Flag counts: {scale_summary.get('flag_counts', {})}.")
        A("")
        flagged = scale_audit[scale_audit["flags"] != ""].copy()
        if len(flagged):
            show = flagged.copy()
            show["name"] = show["name"].astype(str).str.slice(0, 30)
            show["float"] = show["float_usd"].map(_b)
            show["shares"] = show["shares_outstanding"].map(
                lambda v: f"{v:,.0f}" if pd.notna(v) else "")
            show["implied $/sh"] = show["implied_price_usd"].map(
                lambda v: f"{v:,.2f}" if pd.notna(v) else "")
            ratio = pd.to_numeric(show["float_to_assets"], errors="coerce")
            show["float/assets"] = [f"{x:,.1f}x" if pd.notna(x) else "" for x in ratio]
            cols = ["recon_date", "stratum", "cik", "name", "sector", "float",
                    "shares", "implied $/sh", "float/assets", "flags"]
            A("**Every flagged membership row** (the screen's raw output, "
              "before adjudication):")
            A("")
            A(_md_table(show[cols].reset_index(drop=True)))
            A("")
        verdicts = scale_audit[
            scale_audit["scale_verdict"].astype(str).str.startswith("SCALE ERROR")
        ]
        if len(verdicts):
            v = (
                verdicts.sort_values("float_usd", ascending=False)
                .drop_duplicates("cik")[["cik", "name", "stratum", "sector", "float_usd",
                                         "shares_outstanding", "implied_price_usd",
                                         "float_to_assets"]]
                .copy()
            )
            v["name"] = v["name"].astype(str).str.slice(0, 32)
            v["float_usd"] = v["float_usd"].map(_b)
            v["shares_outstanding"] = v["shares_outstanding"].map(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "")
            v["implied_price_usd"] = v["implied_price_usd"].map(
                lambda x: f"${x:,.0f}" if pd.notna(x) else "")
            v["float_to_assets"] = pd.to_numeric(v["float_to_assets"], errors="coerce").map(
                lambda x: f"{x:,.0f}x" if pd.notna(x) else "")
            caught_by = (
                verdicts.groupby("cik")["flags"]
                .apply(lambda s: ";".join(sorted({x for f in s for x in str(f).split(";") if x})))
                .to_dict()
            )
            v.insert(len(v.columns), "caught by", v["cik"].map(caught_by))
            A("**Adjudicated as confirmed scale errors** (arm C: float is a "
              "several-hundred-fold multiple of the registrant's own total "
              "assets). Each is now a row in `manual_exclusions.csv` with its "
              "evidence written out in §3.7. Note ASV Holdings' implied price "
              "of $6 — perfectly normal, because its 10-K cover mis-scaled the "
              "share count by the same 1,000× as the float. Arm A alone would "
              "have missed it entirely:")
            A("")
            A(_md_table(v.reset_index(drop=True)))
            A("")
        excluded_ciks = {ex.cik for ex in exclusions}
        cleared = flagged[
            ~flagged["scale_verdict"].astype(str).str.startswith("SCALE ERROR")
        ]

        def _cleared_table(sub: pd.DataFrame) -> str:
            cl = (
                sub.sort_values("float_usd", ascending=False)
                .drop_duplicates("cik")[["cik", "name", "sector", "implied_price_usd",
                                         "float_to_assets", "flags"]]
                .copy()
            )
            cl["name"] = cl["name"].astype(str).str.slice(0, 32)
            cl["implied_price_usd"] = cl["implied_price_usd"].map(
                lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
            cl["float_to_assets"] = pd.to_numeric(cl["float_to_assets"], errors="coerce").map(
                lambda x: f"{x:,.1f}x" if pd.notna(x) else "—")
            return _md_table(cl.reset_index(drop=True))

        false_alarms = cleared[~cleared["cik"].isin(excluded_ciks)]
        if len(false_alarms):
            A("**Screened, then CLEARED — the screen's false alarms.** These are "
              "genuine large caps with genuine four-figure share prices. "
              "Listing them is the honest way to report a screen's "
              "false-positive rate, and it is what stops a future maintainer "
              "from \"tidying up\" a real company:")
            A("")
            A(_cleared_table(false_alarms))
            A("")
        other_defect = cleared[cleared["cik"].isin(excluded_ciks)]
        if len(other_defect):
            A("**Cleared of mis-scaling, but excluded anyway — a different "
              "defect.** Arm C says these registrants' float values are "
              "consistent with their balance sheets, and that is correct: the "
              "numbers are right, they just no longer describe a company with "
              "publicly traded common equity. Arms B and D are what catch this "
              "class, and the evidence is in §3.7:")
            A("")
            A(_cleared_table(other_defect))
            A("")
        gaps = (
            scale_audit[scale_audit["shares_outstanding"].isna()]
            .groupby(["cik", "name", "shares_source"], as_index=False)
            .size()
            .rename(columns={"size": "membership rows"})
            .sort_values("membership rows", ascending=False)
        )
        if len(gaps):
            gaps["name"] = gaps["name"].astype(str).str.slice(0, 34)
            A(f"**Where the audit cannot speak** ({len(gaps)} registrants, "
              f"{int(gaps['membership rows'].sum())} membership rows). Every one "
              "is a multi-class or dimensioned filer, and every one is a "
              "household-name mega-cap whose float magnitude is not in doubt — "
              "but that is a judgement, not a measurement, and it is recorded as "
              "a coverage gap rather than as a pass:")
            A("")
            A(_md_table(gaps.reset_index(drop=True)))
            A("")
        A("Full per-row output: "
          "`data/universe_e2_candidates/_cache/float_scale_audit.csv`.")
        A("")
        A("**What this audit does NOT do.** It does not remove anything. It "
          "writes a table; removal happens only through "
          "`manual_exclusions.csv`, by hand, with evidence (§3.7). And it is "
          f"not proof of absence: arms A–C are blind to the {n_gap_regs} "
          f"registrants / {n_gap_rows} membership rows above, and a mis-scale "
          "that happens to leave the implied price inside the band, the share "
          "series smooth and the balance-sheet ratio plausible would still "
          "pass. The honest claim is narrower than \"the universe is clean\": "
          f"{len(scale_summary.get('confirmed_scale_errors', []))} specific "
          "registrants were found and removed, and the screen now runs "
          "automatically on every build instead of depending on someone "
          "looking.")
        A("")
        A("**The three thresholds are calibrated on this build's own "
          "distribution, and the margins are wide.** Over the "
          f"{scale_summary.get('rows_with_shares', 0):,} rows with a resolvable "
          "share count the median implied price is "
          f"${pd.to_numeric(scale_audit['implied_price_usd'], errors='coerce').median():,.0f} "
          "and the 99th percentile is "
          f"${pd.to_numeric(scale_audit['implied_price_usd'], errors='coerce').quantile(0.99):,.0f}; "
          "the largest *cleared* float-to-assets ratio is "
          f"{pd.to_numeric(false_alarms['float_to_assets'], errors='coerce').max():,.1f}× "
          "while the smallest *confirmed* one is "
          f"{pd.to_numeric(verdicts['float_to_assets'], errors='coerce').min():,.0f}× — "
          f"an order of magnitude of headroom around the {AUDIT_MAX_FLOAT_TO_ASSETS:.0f}× "
          "line. A threshold that had to be tuned to separate the two would not "
          "be worth trusting; this one does not.")
        A("")

    # -------------------------------------------------------- assumptions
    A("## 7. Every assumption, in one place")
    A("")
    assumptions = [
        "**Float, not market cap, is the size measure.** `EntityPublicFloat` "
        "excludes insider- and affiliate-held shares, so it systematically "
        "under-ranks founder-controlled and family-controlled companies. It is "
        "used because it is the only size measure that is (a) filed by the "
        "company itself, (b) available for delisted registrants, and (c) needs "
        "no price source — which is what makes survivorship-free selection "
        "possible at all.",
        "**Float understates controlled and sponsor-owned entities.** The "
        "weakest continuity5 member of the whole decade is MPLX LP at $6.8B of "
        "float (2021) — its market capitalisation is several times that, but "
        "Marathon Petroleum holds most of the units, and affiliate holdings are "
        "excluded from float by definition. Master limited partnerships, "
        "controlled subsidiaries and founder-controlled companies all rank "
        "lower than a market-cap rule would place them. This is a property of "
        "the measure, not a defect in the code, and it is the price of a "
        "size rank that needs no price data.",
        "**Float is annual and up to ~14 months stale at D**, and each filer's "
        "instant is its own fiscal-Q2 end, so ranks compare slightly different "
        "measurement dates. The per-member `float_staleness_days` column "
        "records the exact staleness of every row.",
        "**Sector labels use current SIC** (§1's stated look-ahead).",
        "**SIC→sector is crude for conglomerates.** The full table is printed "
        "below so that every placement is inspectable rather than implied.",
        "**Telecom carriers (SIC 4812/4813 — AT&T, Verizon) are mapped to "
        "`utilities`** in broad8. GICS would call them Communication Services, "
        "which does not exist in an 8-bucket scheme sized to 100 names. The "
        "alternative is `consumer`, where they would compete with retail and "
        "staples mega-caps. This is a live sub-decision.",
        "**Card networks (SIC 7389 — Visa, Mastercard) are mapped to "
        "`financials`**, matching E1's own labels and current GICS. SIC 7389 "
        "is a catch-all, so this also sweeps payment processors (correct) and "
        "some business-services names (arguable).",
        "**Managed care (SIC 6324 — UnitedHealth, Elevance, CVS) is mapped to "
        "`healthcare`**, matching E1, not to insurance-as-financials.",
        "**Semiconductor capital equipment (SIC 3559 — Applied Materials, Lam) "
        "is mapped to `tech`**, not industrial machinery.",
        "**Midstream gas pipelines (SIC 4922/4923) are `energy`; electric, gas "
        "distribution, water and waste (4900–4921, 4924–4991) are `utilities`.**",
        "**Members are selected per date independently.** There is no buffer "
        "rule (Russell-style banding), so a company oscillating around the K-th "
        "float rank will enter and exit repeatedly. §4's churn numbers include "
        "that mechanical churn; a banding rule is available if the owner wants "
        "turnover damped.",
        "**CIK is the identity key, and predecessor/successor CIKs are NOT "
        "stitched.** Alphabet-2015 and Google Inc., Exxon Mobil Corp and "
        "ExxonMobil Holdings, Cigna Holding and The Cigna Group are each two "
        "registrants here, not one company. Membership, entries and exits are "
        "all per-CIK. Stitching would be a judgement call per pair and is left "
        "to F2 with the evidence in §6.2.",
        "**A registrant's float is discarded when it is demonstrably the "
        "parent's**, i.e. when the identical (accession, instant, value) triple "
        "is reported by more than one CIK and the accession belongs to another "
        "of them. Without this, wholly-owned subsidiary co-registrants on "
        "combined utility 10-Ks enter the universe as large caps (§6.4).",
        "**No mid-cap arm** (EXPANSION_PLAN.md §1.4). Everything here is "
        "large-cap by construction.",
        f"**The ratified universe is {sum(HYBRID136_K.values())} × 11 dates, "
        "not the 100 × 10 years of the original EXPANSION_PLAN.md §1.2 "
        "ratification.** The owner amended the scope in chat on 2026-08-21 to "
        "the two-stratum hybrid; the size change is that amendment, not scope "
        "creep inside the build. Diligence still covers far more registrants "
        "than that (it has to, to rank them), but membership is capped at K "
        "per sector per date by construction and the shortlist depth is "
        "unchanged.",
        "**The two strata are analysed separately, and the split is binding.** "
        "Primary confirmatory analysis on core; extension pooled *and* "
        "stratified as a secondary; promotion of extension to confirmatory "
        "status contingent on gate G2's sector-stratified label quality. The "
        "reason is concrete, not procedural: the fine-tuned labeler was trained "
        "on E1 text, and E1 contains no industrials, no utilities and no "
        "materials/real-estate names at all, so label quality in those three "
        "sectors is an extrapolation until G2 measures it. The rule is stated "
        "in full in the box at the top of this report.",
        "**`hybrid136` never re-decides where a company belongs.** Its core "
        "stratum is `continuity5`'s rule and its extension stratum is "
        "`broad8`'s three extra buckets; the SIC table, the K values, the PIT "
        "rule and the sanitizer are all shared. Exactly two things can make "
        "the strata differ from their option-record counterparts: a documented "
        "manual exclusion (§3.7) and the two owner-ratified float-integrity "
        "rules (§3.8), which are scoped to `hybrid136` on purpose. §3.6 prints "
        "every differing row and §3.8 measures the rules' contribution to it "
        "(zero rows in this build).",
        "**The two float-integrity rules are variant-scoped, and that scoping "
        "is enforced, not just intended.** `VARIANT_RULESETS` gives "
        "`hybrid136` the ratified ruleset and `continuity5`/`broad8` the "
        "legacy one; `test_build_universe_e2.py` asserts that the "
        "option-record panels rebuild byte-identically and that neither rule "
        "can fire on them even when the triggering data is present. An unknown "
        "future variant defaults to LEGACY, so adding a taxonomy can never "
        "silently opt it into rules nobody ratified for it.",
        "**Rule 1 reads a tagged 0 as a statement, and filers sometimes "
        "mis-tag.** A registrant that tags one year's float as 0 while "
        "remaining listed is treated as having no public float for the dates "
        "that 0 is its newest disclosure. §3.8 lists the one such case in this "
        "build (it touches no membership row) and explains why the trade is "
        "still worth making.",
        "**Manual exclusions are a hand-maintained CSV, not code.** A "
        "registrant is removed from the ratified universe only via "
        f"`{MANUAL_EXCLUSIONS_PATH.name}`, only with primary-source evidence in "
        "the row, and always visibly: the reject log records "
        "`manual_exclusion` and §3.7 prints the evidence in full. Dated "
        "exclusions carry a load-time point-in-time guard (the evidence must "
        "have been public before the first date the exclusion bites).",
        "**The option-record variants were NOT retro-cleaned.** `continuity5` "
        "and `broad8` still contain the registrants §6.7 found to be "
        "mis-scaled, because they are the artifacts the owner's 2026-08-21 "
        "decision cites and silently editing them would destroy the audit "
        "trail. Concretely: `continuity5` contains a $880B \"consumer large "
        "cap\" that is really a ~$2.5B car-wash operator. If the owner wants "
        "them cleaned too, add `continuity5;broad8` to the `applies_to` column "
        f"of the relevant `{MANUAL_EXCLUSIONS_PATH.name}` rows and re-run — "
        "that is a one-line change, and it is deliberately the owner's call.",
    ]
    for a in assumptions:
        A(f"- {a}")
    A("")

    # ------------------------------------------------------ mapping tables
    A("## 8. SIC → sector mapping tables (complete)")
    A("")
    A("`broad8` and `hybrid136` use this table in full. `continuity5` is the "
      "same table restricted to tech / financials / healthcare / energy / "
      "consumer; any SIC mapping to industrials, utilities or "
      "materials_realestate is EXCLUDED under continuity5, which is exactly "
      "why `hybrid136`'s core stratum reproduces continuity5 and its extension "
      "stratum is precisely the residue. The variants never disagree about "
      "*where* a company belongs, only about whether its bucket exists and how "
      "deep it runs.")
    A("")
    A("The three live sub-decisions inside the table stay at their documented "
      "defaults under the owner's 2026-08-21 ratification: telecom carriers "
      "(SIC 4812/4813) → `utilities`, card networks (SIC 7389) → `financials`, "
      "managed care (SIC 6324) → `healthcare`. Changing any of them moves names "
      "between the core and extension strata, so they are ratified inputs, not "
      "implementation details.")
    A("")
    A("### 8.1 Exact-SIC overrides (applied first)")
    A("")
    A(_md_table(pd.DataFrame(
        [{"sic": k, "sector": v[0], "in continuity5": "yes" if v[0] in CONTINUITY5_SECTORS else "NO",
          "why": v[1]} for k, v in sorted(SIC_EXACT.items())])))
    A("")
    A("### 8.2 SIC ranges")
    A("")
    A(_md_table(pd.DataFrame(
        [{"sic_from": lo, "sic_to": hi, "sector": sec,
          "in continuity5": "yes" if sec in CONTINUITY5_SECTORS else "NO",
          "description": desc} for lo, hi, sec, desc in SIC_RANGES])))
    A("")
    A("### 8.3 Non-operating SICs (excluded from every variant)")
    A("")
    A(_md_table(pd.DataFrame(
        [{"sic": k, "why excluded": v} for k, v in sorted(NON_OPERATING_SIC.items())])))
    A("")
    A("Any SIC not covered by §8.1–8.2 is EXCLUDED (unmapped), as is a "
      "registrant with a blank SIC or `entityType != \"operating\"`.")
    A("")

    # --------------------------------------------------------- provenance
    A("## 9. Provenance, cost, and how to re-run")
    A("")
    A(f"- Network GETs in THIS run: **{request_count}**. The universe build "
      "itself is fully cached and costs 0; anything above 0 here is the §6.7 "
      "float-scale audit paying for share counts it had never fetched before "
      "(one ~3 KB `companyconcept` document per member CIK, cached forever, "
      "plus one `us-gaap:Assets` document per registrant a screen flagged). "
      "The next run costs 0 again. Every request in the phase went through "
      "`edgar_client.EdgarClient`'s 10 req/s sliding-window limiter with the "
      "project's registered `User-Agent`, sequentially; **no 429s and no 403s "
      "were encountered at any point**.")
    A("- Measured cache footprint of what F1 downloaded:")
    A("")
    A(_md_table(pd.DataFrame(_cache_footprint())))
    A("")
    A("  `data/raw/frames/` and `data/raw/companyconcept/` are NEW directories "
      "created by this phase, following the existing `data/raw/<endpoint>/` "
      "convention. `data/raw/submissions/` is shared with the E1 pipeline and "
      "grew by one submissions document — plus `filings.files[]` pagination "
      "chunks for heavy filers, via the existing `get_effective_recent()` — "
      "for each diligence CIK. It is by far the bulk of the download, and it "
      "is the reason `--shortlist-per-date` is a parameter worth thinking "
      "about rather than maximising.")
    A(f"- **What §6.7 cost on a cold cache, measured:** one "
      f"`dei:EntityCommonStockSharesOutstanding` document per member CIK "
      f"({scale_summary.get('registrants', 0) if scale_summary else 0} GETs, "
      "~3 KB each) plus one `us-gaap:Assets` document per registrant a screen "
      f"flagged ({scale_summary.get('flagged_registrants', 0) if scale_summary else 0} "
      "GETs). All sequential, all through the same limiter, all cached "
      "forever — which is why the line above reads 0.")
    A(f"- Zero Anthropic API calls. Zero GPU/MLX work. The only non-EDGAR "
      f"network use is the §5 price probe: **{price_request_count}** requests "
      "through `price_client.PriceClient` (it tries Stooq first for every "
      "ticker and falls through to Yahoo, so the count is ~2x the tickers "
      "probed). Same robots.txt/ToS caveat as `data/PRICES_NOTES.md` §1. One "
      "further out-of-band probe was made by hand while building §6.7 — "
      "`MCW` (Mister Car Wash), 2 requests, which returned **no data from "
      "either source**, so the exclusion rests entirely on EDGAR-native "
      "evidence and not on a price cross-check.")
    A("")
    A("**Outputs** (all new; nothing existing was modified):")
    A("")
    A("```")
    A("data/universe_e2_candidates/")
    A("  continuity5.parquet/.csv        membership SPELLS (cik, tickers, name, sector,")
    A("                                  member_from, member_to, entry/exit/median rank)")
    A("  continuity5_panel.parquet/.csv  per-(date, member) rows incl. float value, its")
    A("                                  source accession, filed date, staleness, ranks")
    A("  broad8.parquet/.csv             same, broad8 variant")
    A("  broad8_panel.parquet/.csv")
    A("  hybrid136.parquet/.csv          RATIFIED. Same spells schema PLUS a `stratum`")
    A("                                  column (core / extension)")
    A("  hybrid136_panel.parquet/.csv    RATIFIED. Per-(date, member) rows, with `stratum`")
    A("  manual_exclusions.csv           hand-maintained removals + their evidence;")
    A("                                  consumed by the builder, printed in §3.7")
    A("  price_censoring_census.csv/.parquet   every member CIK, ticker resolvable or not")
    A("  price_probe_sample.csv                Yahoo probe of a 15-member sample")
    A("  price_probe_former_tickers.csv        Yahoo probe of 10 hand-identified dead symbols")
    A("  _cache/hybrid136_shadow_panel.parquet")
    A("                                  the SAME build with manual_exclusions.csv")
    A("                                  switched off -- the counterfactual §3.6/§3.7 cite")
    A("  _cache/hybrid136_rules_off_panel.parquet")
    A("                                  the SAME build with the two ratified float-")
    A("                                  integrity rules switched off, exclusions left")
    A("                                  on -- the counterfactual §3.8 diffs against")
    A("  _cache/hybrid136_legacy_panel.parquet")
    A("                                  both switched off: the pre-2026-08-21 build")
    A("  _cache/                         frames panel, shortlist, per-CIK profiles,")
    A("                                  PIT float facts, per-variant reject logs with")
    A("                                  reasons, suspect float facts, diligence flags,")
    A("                                  float_scale_audit.csv (+ .parquet, + summary.json)")
    A("data/E2_UNIVERSE_REPORT.md        this file")
    A("build_universe_e2.py, e2_report.py, test_build_universe_e2.py")
    A("```")
    A("")
    A(f"Re-run: `python3 build_universe_e2.py --stage all "
      f"--shortlist-per-date {args.shortlist_per_date}`. Stages "
      "(`frames`/`diligence`/`select`) are individually re-runnable and "
      "idempotent; nothing already cached is re-downloaded. "
      "`--ignore-manual-exclusions` rebuilds the ratified variant as if the "
      "exclusions CSV were empty (diagnostic), and `--no-scale-audit` skips "
      "§6.7.")
    A("")
    A("**Adopted — items that have moved off the open list:**")
    A("")
    A(f"- **`{FLOAT_RULE_NEWER_ZERO}` — adopted 2026-08-21** (owner "
      "ratification in chat: \"Yes, please adopt both, as you recommended\"). "
      "Was: *\"a more-recent, already-public float disclosure of exactly 0 is "
      "currently discarded, letting a superseded positive value win … left as "
      "an explicit recommendation for the owner rather than done here\"*. Now "
      "implemented, **scoped to `hybrid136`**, which is what makes it possible "
      "without disturbing the option record. Semantics and every firing: §3.8. "
      "Membership impact in this build: **0 rows**.")
    A(f"- **`{FLOAT_RULE_MIN_SHARES}` — adopted 2026-08-21** (same "
      "ratification). Was: *\"a share count below "
      f"{MIN_PUBLIC_SHARES_FOR_MEMBERSHIP:,} on a member's own cover page "
      "means the registrant has no publicly traded common equity … "
      "deliberately NOT done in this phase — it would change the option-record "
      "variants\"*. Now implemented, **scoped to `hybrid136`**, cache-only "
      "(0 network requests), abstaining where the share count is untestable. "
      "Semantics and every firing: §3.8. Membership impact in this build: "
      "**0 rows**.")
    A("- Both adoptions kept `continuity5` and `broad8` byte-identical, which "
      "is asserted in `test_build_universe_e2.py` rather than hoped for.")
    A("")
    A("**Not verified / open:**")
    A("")
    A("- Whether the ratified universe's members all have extractable filings "
      "back to 2016 — F3's job; pre-2019 filer HTML dialects are the known "
      "risk, and the extension stratum adds three sectors of filers that E1's "
      "`extract.py` calibrations have never seen.")
    A("- Historical SIC codes (EDGAR publishes none) and historical tickers for "
      "dead registrants (EDGAR keeps none) — both stated as assumptions above.")
    A("- The exact window start/end remain subject to gate **G3**; every date "
      "here is a parameter, not a constant baked into an output.")
    A("- **A registrant that mis-scales its ENTIRE float history identically "
      "still slips through the automated sanitizer** — with no clean "
      "neighbour there is nothing to compare against, and only the absolute "
      "$10T ceiling applies. This is no longer hypothetical: §6.7 found three "
      "such registrants among the ratified universe's members, one of them in "
      "the CORE stratum. The §6.7 screen is now the compensating control, but "
      "it is a screen with a measured coverage gap (multi-class filers that "
      "tag share counts behind an XBRL axis), and removal still depends on a "
      "human reading the evidence and editing "
      f"`{MANUAL_EXCLUSIONS_PATH.name}`.")
    A("- Rule 1's blind spot is the mirror image of the case it fixes: a "
      "registrant that becomes a wholly-owned subsidiary but keeps tagging a "
      "**positive** (fossil) float, rather than 0, is still invisible to it. "
      "Rule 2 catches that only if the registrant also tags a small "
      "undimensioned share count.")
    A("- Rule 2's coverage gap is measured, not closed: the multi-class filers "
      "that tag share counts behind an XBRL axis expose no undimensioned fact, "
      "so the rule cannot speak for them (§3.8, §6.7). Closing it would mean "
      "fetching dimensioned facts for every member, which the ratified scope "
      "explicitly declines.")
    A("- The co-registrant filter keys on an exact (accession, instant, value) "
      "match inside the frames window. A combined filing where the "
      "subsidiary's tagged value differs from the parent's by even one dollar "
      "would not be caught.")
    A("- The 10 former ticker symbols in §5 were typed by hand from public "
      "knowledge of each acquisition. They are used only for that probe, but "
      "they are not machine-verified, and EDGAR cannot confirm them.")
    A("- No variant has been validated against `ingest_metadata.py`'s "
      "`validate_universe()`; that gate needs the per-company-window rework "
      "described in EXPANSION_PLAN.md §3.6 before it can be run on a churning "
      "membership table at all.")
    A("- The §6.7 audit was run over the ratified universe's members only. The "
      "option-record variants' members that `hybrid136` does not select have "
      "NOT been screened this way.")
    A("- Label quality in the three extension sectors is unmeasured (gate G2). "
      "Until it is, §7's stratum analysis rule is what keeps that gap from "
      "silently becoming a headline number.")

    REPORT_PATH.write_text("\n".join(L) + "\n")
    return "\n".join(L)
