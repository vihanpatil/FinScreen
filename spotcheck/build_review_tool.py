"""
build_review_tool.py — assembles spotcheck/review_tool.html from:
  - review_app_template.html  (the DOM/CSS/JS shell, with placeholders)
  - review_app.js             (the pure serialization/state logic, tested
                                under Node by test_review_app.js)
  - sample_400.json           (the 400 examples, produced by
                                export_sample_json.py)

Run this after any change to review_app.js, review_app_template.html, or
sample_400.json. Produces a single self-contained review_tool.html with
everything inlined — no external hosts, works from file://.
"""

import json

BASE = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck"

with open(f"{BASE}/review_app_template.html") as f:
    template = f.read()
with open(f"{BASE}/review_app.js") as f:
    app_js = f.read()
with open(f"{BASE}/sample_400.json") as f:
    sample_json_text = f.read()
    json.loads(sample_json_text)  # validate

out = template.replace("/*__REVIEW_APP_JS__*/", app_js)
out = out.replace("/*__SAMPLE_DATA_JSON__*/", sample_json_text)

with open(f"{BASE}/review_tool.html", "w") as f:
    f.write(out)

print(f"Wrote {BASE}/review_tool.html ({len(out)} bytes)")
