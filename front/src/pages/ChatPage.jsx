import { useState } from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import "../components/ChatPage.css";

const REQUIRED_FIELDS = ["age","household_size","marriage","tenure_type","no_house","income_monthly","asset_total","job_yn","debt_yn"];

export default function ChatPage({ onResult, onHome, isLoggedIn, onLogout, onMypage }) {
  const [history, setHistory] = useState([
    { role:"assistant", content:"안녕하세요! 몇 가지 여쭤보고 맞는 정책을 찾아드릴게요. 나이가 어떻게 되세요?" }
  ]);
  const [input, setInput] = useState("");
  const [collected, setCollected] = useState({});
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!input.trim() || loading) return;
    const newHistory = [...history, { role:"user", content: input }];
    setHistory(newHistory);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ history: newHistory })
      });
      const data = await res.json();
      setHistory([...newHistory, { role:"assistant", content: data.reply }]);
      setCollected(data.collected || {});

      if (data.ready_to_predict) {
        const pred = await fetch("/api/predict", {
          method: "POST",
          headers: { "Content-Type":"application/json" },
          body: JSON.stringify(data.collected)
        });
        onResult(await pred.json());
      }
    } catch(e) {
      const msg = e?.message?.includes("Failed to fetch")
        ? "서버에 연결할 수 없어요. 잠시 후 다시 시도해주세요."
        : "오류가 발생했어요. 다시 시도해주세요.";
      setHistory(prev => [...prev, { role:"assistant", content: msg, isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  const handleHome = () => {
    const hasProgress = history.length > 1 || Object.keys(collected).length > 0;
    if (hasProgress) {
      if (!window.confirm("진행 중인 상담 내용은 저장되지 않습니다.\n홈으로 돌아가시겠습니까?")) return;
    }
    onHome();
  };

  const done = Object.keys(collected).length;
  const total = REQUIRED_FIELDS.length;
  const progress = Math.floor((done / total) * 5);

  return (
    <div className="chat-wrap">
      <Navbar
        isLoggedIn={isLoggedIn}
        onHome={handleHome}
        onLogout={onLogout}
        onMypage={onMypage}
      />
      <div className="chat-layout">
        <div className="chat-main">
          <div className="chat-topbar">
            <div className="chat-avatar">✦</div>
            <span className="chat-title">AI 정책 상담</span>
          </div>

          <div className="step-bar">
            {Array.from({length:5}).map((_,i) => (
              <div key={i} className={`step ${i < progress ? "done" : i === progress ? "cur" : ""}`} />
            ))}
            <span className="step-label">정보 수집 중 {done}/{total}</span>
          </div>

          <div className="messages">
            {history.map((m, i) => (
              <div key={i} className={`bw ${m.role === "user" ? "me" : ""}`}>
                {m.role === "assistant" && <div className="av-sm">✦</div>}
                <div className={`bubble ${m.role === "user" ? "me" : m.isError ? "bot error" : "bot"}`}>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="bw">
                <div className="av-sm">✦</div>
                <div className="bubble bot typing">
                  <div className="typing-dots">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="chat-input">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && send()}
              placeholder="입력하세요 — 한 번에 다 말해도 돼요"
            />
            <button onClick={send} disabled={loading}>전송</button>
          </div>
        </div>

        <Sidebar collected={collected} total={total} done={done} />
      </div>
    </div>
  );
}
