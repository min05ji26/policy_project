import "../components/Sidebar.css";

const GROUPS = [
  { label:"기본", keys:["age","household_size","marriage"] },
  { label:"주거", keys:["tenure_type","no_house"] },
  { label:"경제", keys:["income_monthly","asset_total","job_yn","debt_yn"] },
];

const KEY_LABEL = {
  age:"나이", household_size:"가구원수", marriage:"혼인",
  tenure_type:"거주형태", no_house:"무주택",
  income_monthly:"소득", asset_total:"자산", job_yn:"취업", debt_yn:"부채"
};

export default function Sidebar({ collected, done, total, onAnalyze }) {
  const ready = done >= total;

  return (
    <div className="sidebar">
      <div className="sidebar-hd">수집된 정보</div>
      <div className="sidebar-body">
        {GROUPS.map(g => (
          <div key={g.label} className="chip-group">
            <div className="chip-group-label">{g.label}</div>
            <div className="chip-row">
              {g.keys.map(k => (
                <span key={k} className={`chip ${collected[k] ? "filled" : "empty"}`}>
                  {collected[k] ? `${KEY_LABEL[k]} ${collected[k]}` : `${KEY_LABEL[k]} ?`}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="sidebar-footer">
        <button
          className={`analyze-btn ${ready ? "on" : ""}`}
          onClick={ready ? onAnalyze : undefined}
          disabled={!ready}
        >
          분석 시작하기 →
        </button>
        {!ready && (
          <p className="sidebar-note">정보가 모이면 활성화돼요</p>
        )}
      </div>
    </div>
  );
}