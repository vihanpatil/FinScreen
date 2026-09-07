#!/bin/bash
# Worker for a disjoint half of the 10-Q shard set (P1 §6: 2 workers max,
# split by shard index, never two workers on the same index).
cd /Users/vihanpatil/personal/projects/FinScreen
for i in $(seq "$1" "$2"); do
  python3 extract.py --segment 10-Q --shard "$i" --out-dir data/f3/v2 \
      --out-parquet data/filings_e2_v2.parquet
done
echo "WORKER $1-$2 DONE $(date -u +%FT%TZ)"
