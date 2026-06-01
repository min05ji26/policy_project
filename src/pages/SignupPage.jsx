import { useState } from "react";
import Navbar from "./Navbar";
import "../components/SignupPage.css";

export default function SignupPage({ onGoLogin, onHome }) {
  const [form, setForm] = useState({ email:"", password:"", passwordConfirm:"", nickname:"" });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const set = (k, v) => setForm(prev => ({ ...prev, [k]:v }));

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.email || !form.password || !form.nickname) { setError("모든 항목을 입력해주세요."); return; }
    if (form.password !== form.passwordConfirm) { setError("비밀번호가 일치하지 않아요."); return; }
    if (form.password.length < 8) { setError("비밀번호는 8자 이상이어야 해요."); return; }

    // 백엔드 연결 시 여기서 POST /auth/signup
    // const res = await fetch("http://localhost:8000/auth/signup", {
    //   method:"POST",
    //   headers:{ "Content-Type":"application/json" },
    //   body: JSON.stringify({ email:form.email, password:form.password, nickname:form.nickname })
    // });
    // const data = await res.json();
    // if (res.ok) { setDone(true); }
    // else { setError(data.detail); }

    setDone(true);
  };

  if (done) return (
    <div className="signup-wrap">
      <Navbar onHome={onHome} />
      <div className="signup-container">
        <div className="signup-card">
          <div className="done-icon">✓</div>
          <h2 className="done-title">가입 완료!</h2>
          <p className="done-sub">이제 로그인하고 분석 결과를 저장해보세요</p>
          <button className="signup-submit" onClick={onGoLogin}>로그인하러 가기</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="signup-wrap">
      <Navbar onHome={onHome} />
      <div className="signup-container">
        <div className="signup-card">
          <div className="signup-header">
            <h2 className="signup-title">회원가입</h2>
            <p className="signup-sub">가입 후 분석 결과를 저장할 수 있어요</p>
          </div>

          <form onSubmit={handleSignup} className="signup-form">
            <div className="field">
              <label>닉네임</label>
              <input
                type="text"
                placeholder="사용할 닉네임"
                value={form.nickname}
                onChange={e => set("nickname", e.target.value)}
              />
            </div>
            <div className="field">
              <label>이메일</label>
              <input
                type="email"
                placeholder="example@email.com"
                value={form.email}
                onChange={e => set("email", e.target.value)}
              />
            </div>
            <div className="field">
              <label>비밀번호</label>
              <input
                type="password"
                placeholder="8자 이상"
                value={form.password}
                onChange={e => set("password", e.target.value)}
              />
            </div>
            <div className="field">
              <label>비밀번호 확인</label>
              <input
                type="password"
                placeholder="비밀번호 재입력"
                value={form.passwordConfirm}
                onChange={e => set("passwordConfirm", e.target.value)}
              />
            </div>
            {error && <p className="error-msg">{error}</p>}
            <button type="submit" className="signup-submit">가입하기</button>
          </form>

          <div className="signup-footer">
            <span>이미 계정이 있으신가요?</span>
            <button className="go-login" onClick={onGoLogin}>로그인</button>
          </div>
        </div>
      </div>
    </div>
  );
}