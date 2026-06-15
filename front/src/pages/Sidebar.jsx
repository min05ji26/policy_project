// Sidebar는 ChatPage.css에서 스타일 적용됨

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

export default function Sidebar({ collected, done, total }) {
  const allKeys = GROUPS.flatMap(g => g.keys);
  return (
    <div className="sidebar">
      <div className="sidebar-title">수집된 정보 {done}/{total}</div>
      {allKeys.map(k => (
        <div key={k} className="sidebar-item">
          <span className="sidebar-key">{KEY_LABEL[k]}</span>
          {collected[k]
            ? <span className="sidebar-val">{collected[k]}</span>
            : <span className="sidebar-empty">—</span>
          }
        </div>
      ))}
    </div>
  );
}
