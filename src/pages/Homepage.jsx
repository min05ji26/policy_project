import { useState } from "react";
import Navbar from "./Navbar";
import "../components/Homepage.css";

const POLICIES = [
  { tag:"대출", tagClass:"tag-loan", name:"청년 월세 대출", desc:"보증금·월세 부담 경감, 주택도시기금 연 1.5%", site:"nhuf.molit.go.kr", url:"https://nhuf.molit.go.kr" },
  { tag:"대출", tagClass:"tag-loan", name:"버팀목 전세자금대출", desc:"무주택 세대주 저금리 전세자금, 최대 1.2억", site:"nhuf.molit.go.kr", url:"https://nhuf.molit.go.kr" },
  { tag:"임대", tagClass:"tag-rental", name:"공공임대주택", desc:"LH·SH 장기 저렴 임대, 시세 40~80%", site:"apply.lh.or.kr", url:"https://apply.lh.or.kr" },
  { tag:"분양", tagClass:"tag-supply", name:"공공분양", desc:"시세 이하 분양, 청년 특별공급 포함", site:"apply.lh.or.kr", url:"https://apply.lh.or.kr" },
  { tag:"급여", tagClass:"tag-benefit", name:"주거급여 임차", desc:"중위소득 48% 이하, 월 임차료 지원", site:"bokjiro.go.kr", url:"https://bokjiro.go.kr" },
  { tag:"대출", tagClass:"tag-loan", name:"디딤돌 구입자금", desc:"생애 최초 주택 구입, 연 1.85~3.0%", site:"nhuf.molit.go.kr", url:"https://nhuf.molit.go.kr" },
];

const TABS = ["전체","청년","주거","취업지원","저소득"];

export default function HomePage({ onStart }) {
  const [tab, setTab] = useState("전체");

  return (
    <div className="home-wrap">
      <Navbar />
      <div className="hero">
        <div className="hero-eyebrow">AI 정책 추천 서비스</div>
        <h1 className="hero-title">
          내 조건에 맞는<br/>
          <span className="hero-accent">정책</span>을 찾아드려요
        </h1>
        <p className="hero-sub">복잡한 조건 계산 없이, AI와 대화하면<br/>수혜 가능성이 높은 정책을 바로 알 수 있어요</p>
        <button className="hero-cta" onClick={onStart}>
          AI 챗봇으로 시작하기
        </button>
        <p className="hero-cta-sub">로그인 없이 바로 이용할 수 있어요</p>
      </div>

      <div className="home-body">
        <div className="tab-row">
          {TABS.map(t => (
            <button key={t} className={`tab ${tab === t ? "on" : ""}`} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="sec-title">정책 모음</div>
        <div className="policy-grid">
          {POLICIES.map(p => (
            <div key={p.name} className="pc" onClick={() => window.open(p.url, "_blank")}>
              <span className={`pc-tag ${p.tagClass}`}>{p.tag}</span>
              <div className="pc-name">{p.name}</div>
              <div className="pc-desc">{p.desc}</div>
              <div className="pc-site">↗ {p.site}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}