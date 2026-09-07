#!/bin/bash
set -e
cd /Users/vihanpatil/personal/projects/FinScreen
OUT=data/f3/v2
PQ=data/filings_e2_v2.parquet
for SEG in earnings 10-K 10-Q; do
  echo "=== segment $SEG $(date -u +%FT%TZ) ==="
  python3 extract.py --segment "$SEG" --out-dir "$OUT" --out-parquet "$PQ"
done
echo "=== merge $(date -u +%FT%TZ) ==="
python3 extract.py --merge --out-dir "$OUT" --out-parquet "$PQ"
echo "=== ALL DONE $(date -u +%FT%TZ) ==="
