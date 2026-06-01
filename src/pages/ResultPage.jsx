import Navbar from "./Navbar";
import "../components/ResultPage.css";

export default function ResultPage({ result, onReset, onHome }) {
  if (!result) return null;
  const { overall_prob, policies } = result;
  const pct = Math.round(overall_prob * 100);

  return (
    <div className="result-wrap">
      <Navbar onHome={onHome} />
      <div className="res-top">
        <div className="res-num-wrap">
          <div className="res-big">{pct}%</div>
          <div className="res-label">전체 수혜 가능성</div>
        </div>
        <div className="res-divider" />
        <div className="res-summary">
          <div className="res-badge">
            ✦ {policies.filter(p => p.prob >= 0.5).length}개 정책 50% 이상
          </div>
          <div className="res-desc">
            가능성이 낮더라도 자격이 되는 정책은 꼭 신청해보세요.
          </div>
        </div>
        <button className="res-rerun" onClick={onReset}>다시 분석</button>
      </div>

      <div className="res-body">
        <div className="res-list">
          {[...policies].sort((a,b) => b.prob - a.prob).map((p, i) => (
            <div key={p.key} className={`rc ${i === 0 ? "top" : ""}`}>
              <div className="rc-left">
                <div className={`rc-rank ${p.is_paradox ? "paradox" : ""}`}>
                  {p.is_paradox ? "자격 있는데 미수혜" : `추천 ${i+1}순위`}
                </div>
                <div className="rc-name">{p.name}</div>
                <div className="rc-bar-bg">
                  <div className={`rc-bar ${p.is_paradox ? "warn" : ""}`}
                    style={{ width:`${Math.round(p.prob*100)}%` }} />
                </div>
              </div>
              <div className="rc-right">
                <div className={`rc-prob ${p.is_paradox ? "warn" : ""}`}>
                  {Math.round(p.prob * 100)}%
                </div>
                <a className="rc-link" href={p.apply_url} target="_blank" rel="noopener noreferrer">
                  ↗ 신청 사이트
                </a>
              </div>
            </div>
          ))}
        </div>

        <div className="save-row">
          <span className="save-txt">이 결과를 저장하고 싶다면 로그인하세요</span>
          <button className="save-btn">로그인하고 저장하기</button>
        </div>
      </div>
    </div>
  );
}