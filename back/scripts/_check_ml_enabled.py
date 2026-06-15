import json
with open("data/policies_meta.json", encoding="utf-8") as f:
    meta = json.load(f)

enabled = [(k, v.get("ml_beneficiary_count")) for k, v in meta.items()
           if k != "_meta" and v.get("ml_enabled")]
print("=== ml_enabled=true ===")
for k, cnt in enabled:
    print(f"  {k}  (수혜자 {cnt}건)")

v = meta["주거급여임차"]
print("\n=== 주거급여임차 변경 확인 ===")
print(f"  ml_enabled        : {v['ml_enabled']}")
print(f"  ml_disabled_reason: {v['ml_disabled_reason']}")
print(f"  ml_disabled_date  : {v['ml_disabled_date']}")
