"""
생계급여 3-턴 대화 세션 테스트
턴 1: 정책 요청
턴 2: 일부 정보 제공
턴 3: 나머지 정보 제공 → 완료
"""
import requests, json

BASE = "http://localhost:8000"
SID  = None

def chat(msg, sid=None):
    body = {"message": msg}
    if sid:
        body["session_id"] = sid
    r = requests.post(f"{BASE}/chat", json=body, timeout=60)
    d = r.json()
    print(f"\n[사용자] {msg}")
    print(f"[상담사] {d.get('message', '')}")
    print(f"  status        : {d.get('status')}")
    print(f"  session_id    : {d.get('session_id')}")
    print(f"  missing_fields: {d.get('missing_fields', [])}")
    collected = d.get("collected_info", {})
    filled = {k: v for k, v in collected.items() if v is not None}
    print(f"  collected({len(filled)}/{len(collected)}): {filled}")
    if d.get("result"):
        r2 = d["result"]
        print(f"\n  === 최종 결과 ===")
        print(f"  정책     : {r2.get('정책')}")
        print(f"  수혜확률 : {r2.get('수혜확률')}%")
        print(f"  자격충족 : {r2.get('자격충족')}")
        print(f"  수혜수준 : {r2.get('수혜수준')}")
        print(f"  답변:\n  {r2.get('answer')}")
    return d.get("session_id")

print("=" * 60)
print("생계급여 3-턴 대화 테스트")
print("=" * 60)

# 턴 1: 정책 요청
SID = chat("나 생계급여 받을 수 있는지 알고 싶어")

# 턴 2: 가구·소득 정보 제공
SID = chat("저는 혼자 살고 있고 월소득은 20만원이에요. 재산은 300만원 정도입니다.", SID)

# 턴 3: 나머지 정보 제공
SID = chat("장애인은 아니고, 65세 넘었어요.", SID)
