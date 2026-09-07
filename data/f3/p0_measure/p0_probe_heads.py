"""Same deterministic sample as probe.py 6, but stores head/tail text so the
anchor-slice head check and over-capture tail check can be MEASURED."""
import json, sys, time
from pathlib import Path
ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen"); sys.path.insert(0, str(ROOT))
import extract as E
from p0_probe_periodic import CacheClient, sample_periodic
cl = CacheClient()
picks = sample_periodic(6)
recs=[]; t0=time.time()
for acc, cik, ticker, form, fdate, pdoc in picks:
    for section in ("MDA","RISK_FACTORS"):
        try:
            res = E.extract_item_section(cl, int(cik), acc, pdoc, form, section)
        except Exception as e:
            res=None
        recs.append(dict(acc=acc,cik=cik,form=form,year=fdate[:4],section=section,
            ok=res is not None, method=res.method if res else None,
            conf=res.confidence if res else None,
            words=len(res.text.split()) if res else 0,
            head=res.text[:400] if res else "", tail=res.text[-400:] if res else ""))
print("wall %.0fs" % (time.time()-t0))
Path("probe2.json").write_text(json.dumps(recs))
