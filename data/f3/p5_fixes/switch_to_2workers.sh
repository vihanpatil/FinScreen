#!/bin/bash
cd /Users/vihanpatil/personal/projects/FinScreen
# wait for all 10 10-K shards
while [ "$(ls data/f3/v2/shards/ | grep -c '10-K.*done')" -lt 10 ]; do sleep 30; done
echo "10-K complete $(date -u +%FT%TZ)"
pkill -f run_v2.sh; sleep 2
pkill -f "extract.py --segment 10-Q"; sleep 3
nohup bash data/f3/p5_fixes/run_v2_10q.sh 0 7  > data/f3/p5_fixes/run_v2_10q_a.log 2>&1 &
nohup bash data/f3/p5_fixes/run_v2_10q.sh 8 15 > data/f3/p5_fixes/run_v2_10q_b.log 2>&1 &
echo "workers launched $(date -u +%FT%TZ)"
wait
