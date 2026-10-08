from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2]
try:from guide_cartridge import verify
except ImportError:
 sys.path.insert(0,str(ROOT/'package/guide-installer'));from guide_cartridge import verify
folder=ROOT/'build/cartridge-installer-0/corpus';cases=json.loads((folder/'cases.json').read_text())
for case in cases:
 try:
  with (folder/case['file']).open('rb') as f:verify(f)
  accepted=True
 except Exception:accepted=False
 assert accepted==case['accepted'],case['file']
print('ARM64_COMMON_CORPUS_PASS',len(cases))
