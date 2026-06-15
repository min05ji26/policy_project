import Navbar from "./Navbar";
import "../components/ResultPage.css";

export default function ResultPage({ result, onReset, onHome, isLoggedIn, onLogin }) {
  if (!result) return null;

  const { overall_prob, policies = [] } = result;
  const pct = Math.round((overall_prob || 0) * 100);

  const sorted   = [...policies].sort((a, b) => b.prob - a.prob);
  const eligible = sorted.filter(p => p.eligible);
  const highCount = eligible.filter(p => p.prob >= 0.5).length;

  function barColor(p) {
    if (p.is_paradox) return "warn";
    if (p.prob < 0.2)  return "low";
    return "";
  }

  function probClass(p) {
    if (p.is_paradox)  return "warn";
    if (p.prob >= 0.5) return "high";
    if (p.prob < 0.2)  return "low";
    return "";
  }

  function rankLabel(p, i) {
    if (p.is_paradox) return { text: "자격 있는데 미수혜 ⚠", cls: "paradox-label" };
    if (i === 0 && p.eligible) return { text: "✦ 최우선 추천", cls: "top-label" };
    return { text: `추천 ${i + 1}순위`, cls: "" };
  }

  return (
    <div className="result-wrap">
      <Navbar isLoggedIn={isLoggedIn} onLogout={() => {}} onHome={onHome} />

      <div className="res-top">
        <div className="res-num-wrap">
          <div className="res-big">{pct}%</div>
          <div className="res-label">전체 수혜 가능성</div>
        </div>

        <div className="res-divider" />

        <div className="res-summary">
          <div className={`res-badge ${highCount === 0 ? "warn" : ""}`}>
            ✦ {highCount > 0
              ? `${highCount}개 정책 50% 이상`
              : "자격 조건을 다시 확인해보세요"}
          </div>
          <div className="res-desc">
            {eligible.length > 0
              ? `자격 충족 정책 ${eligible.length}개 · 가능성이 낮아도 신청해두는 게 좋아요.`
              : "현재 입력 정보 기준으로 자격 충족 정책이 없어요. 조건이 달라지면 다시 분석해보세요."}
          </div>
        </div>

        <button className="res-rerun" onClick={onReset}>다시 분석</button>
      </div>

      <div className="res-body">
        <div className="res-section-title">정책별 수혜 가능성</div>
        <div className="res-list">
          {sorted.map((p, i) => {
            const rank = rankLabel(p, i);
            return (
              <div
                key={p.key}
                className={`rc${i === 0 && p.eligible ? " top" : ""}${p.is_paradox ? " paradox" : ""}${!p.eligible ? " ineligible" : ""}`}
              >
                <div className="rc-left">
                  <div className={`rc-rank ${rank.cls}`}>{rank.text}</div>
                  <div className="rc-name">{p.name}</div>
                  <div className="rc-bar-bg">
                    <div
                      className={`rc-bar ${barColor(p)}`}
                      style={{ width: `${Math.round(p.prob * 100)}%` }}
                    />
                  </div>
                </div>

                <div className="rc-right">
                  <div className={`rc-prob ${probClass(p)}`}>
                    {Math.round(p.prob * 100)}%
                  </div>
                  <a
                    className="rc-link"
                    href={p.apply_url || "https://www.bokjiro.go.kr"}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    ↗ 신청 사이트
                  </a>
                </div>
              </div>
            );
          })}
        </div>

        {!isLoggedIn && (
          <div className="save-row">
            <span className="save-txt">결과를 저장하고 나중에 다시 확인하고 싶다면 로그인하세요</span>
            <button className="save-btn" onClick={onLogin}>로그인하고 저장하기</button>
          </div>
        )}
      </div>
    </div>
  );
}