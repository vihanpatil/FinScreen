#!/bin/bash
# P5 rebuild, 4 disjoint workers. Determinism is unaffected: each shard is an
# independent pure function of one cached document plus fixed constants.
cd /Users/vihanpatil/personal/projects/FinScreen
O="--out-dir data/f3/v2 --out-parquet data/filings_e2_v2.parquet"
case "$1" in
  A) python3 extract.py --segment earnings $O
     for i in 0 1 2 3 4; do python3 extract.py --segment 10-K --shard $i $O; done ;;
  B) for i in 5 6 7 8 9; do python3 extract.py --segment 10-K --shard $i $O; done
     for i in 0 1 2 3; do python3 extract.py --segment 10-Q --shard $i $O; done ;;
  C) for i in 4 5 6 7 8 9; do python3 extract.py --segment 10-Q --shard $i $O; done ;;
  D) for i in 10 11 12 13 14 15; do python3 extract.py --segment 10-Q --shard $i $O; done ;;
esac
echo "WORKER $1 DONE $(date -u +%FT%TZ)"
