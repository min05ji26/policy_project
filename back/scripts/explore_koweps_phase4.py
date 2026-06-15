"""h20_g*, h20_soc_*, h20_eco* 라벨 확인"""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')
import pyreadstat

KOWEPS_PATH = os.getenv('KOWEPS_DATA_PATH')
_, meta = pyreadstat.read_dta(KOWEPS_PATH, metadataonly=True)
lbl = dict(zip(meta.column_names, meta.column_labels))

print("=== h20_g* ===")
for v in sorted(c for c in meta.column_names if c.startswith('h20_g')):
    print(f"  {v:22s} {lbl.get(v,'')}")

print()
print("=== h20_eco* ===")
for v in sorted(c for c in meta.column_names if c.startswith('h20_eco')):
    print(f"  {v:22s} {lbl.get(v,'')}")

print()
print("=== h20_soc* / h20_med* ===")
for v in sorted(c for c in meta.column_names if c.startswith(('h20_soc','h20_med'))):
    print(f"  {v:22s} {lbl.get(v,'')}")
