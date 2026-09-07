"""Copy the real cached bytes `test_extract_e2.py` pins into data/f3/fixtures/.

Same convention as data/f2/fixtures/build_fixtures.py: real EDGAR bytes, small
files copied whole, large ones stored as truncated prefixes. Zero GETs -- every
byte comes from data/raw/documents/, which F2 populated.

Re-run:  python3 data/f3/fixtures/build_fixtures.py
"""
import shutil
from pathlib import Path

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
DOCS = ROOT / "data/raw/documents"
OUT = Path(__file__).parent

# (fixture name, cache key, prefix bytes or None for whole file, why)
FIXTURES = [
    ("ice_bakkt_0001104659-22-112514_8k.htm",
     "Archives_edgar_data_1571949_000110465922112514_tm2229179d1_8k.htm", None,
     "The population gate's decisive row: ICE furnishing BAKKT's results. "
     "H4 verdict C; the narrowed signature variant fails to flag it (T6)."),
    ("humana_0000049071-16-000113_8k.htm",
     "Archives_edgar_data_49071_000004907116000113_humana8-k01082016.htm", None,
     "8K_BODY whose item-2.02 block is 8 words before Item 7.01 -- the census's "
     "thinnest block, and why the slice ends at EOD, not the next heading (T7)."),
    ("smallest10q_0001193125-17-021855_10q.htm",
     "Archives_edgar_data_1222333_000119312517021855_d289743d10q.htm", None,
     "A real anchor-TOC 10-Q, both sections located; the parse-once equivalence "
     "and end-to-end run fixtures (T2, T4, T15-T17)."),
    ("usbancorp_0001193125-17-053947_10k.htm",
     "Archives_edgar_data_36104_000119312517053947_d291857d10k.htm", None,
     "US Bancorp 2017: a 50-word MD&A stub located by the HEADING-REGEX "
     "fallback whose reference language reads 'incorporated INTO THIS REPORT by "
     "reference'. E1's language gate missed it entirely (T10)."),
]


def main():
    for name, key, prefix, _why in FIXTURES:
        src = DOCS / key
        if not src.exists():
            print(f"MISSING {key}")
            continue
        dst = OUT / name
        if prefix is None:
            shutil.copyfile(src, dst)
        else:
            dst.write_bytes(src.read_bytes()[:prefix])
        print(f"{dst.name}  {dst.stat().st_size:>9,} bytes")


if __name__ == "__main__":
    main()
