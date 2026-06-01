import { useState } from "react";
import Navbar from "./Navbar";
import "../components/LoginPage.css";

export default function LoginPage({ onLogin, onGoSignup, onHome }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    if (!email || !password) { setError("이메일과 비밀번호를 입력해주세요."); return; }

    // 백엔드 연결 시 여기서 POST /auth/login
    // const res = await fetch("http://localhost:8000/auth/login", {
    //   method:"POST",
    //   headers:{ "Content-Type":"application/json" },
    //   body: JSON.stringify({ email, password })
    // });
    // const data = await res.json();
    // if (data.access_token) {
    //   localStorage.setItem("token", data.access_token);
    //   onLogin();
    // } else { setError(data.detail); }

    // 임시 mock
    onLogin();
  };

  return (
    <div className="login-wrap">
      <Navbar onHome={onHome} />
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="login-logo">정책포털</div>
            <h2 className="login-title">로그인</h2>
            <p className="login-sub">분석 결과를 저장하고 다시 확인하세요</p>
          </div>

          <div className="social-btns">
            <button className="social-btn kakao">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 1.5C4.86 1.5 1.5 4.09 1.5 7.27c0 2.03 1.35 3.81 3.38 4.83l-.86 3.2 3.74-2.46c.4.06.81.09 1.24.09 4.14 0 7.5-2.59 7.5-5.77S13.14 1.5 9 1.5z" fill="#3C1E1E"/>
              </svg>
              카카오로 로그인
            </button>
          </div>

          <div className="divider"><span>또는</span></div>

          <form onSubmit={handleLogin} className="login-form">
            <div className="field">
              <label>이메일</label>
              <input
                type="email"
                placeholder="example@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>
            <div className="field">
              <label>비밀번호</label>
              <input
                type="password"
                placeholder="비밀번호 입력"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="error-msg">{error}</p>}
            <button type="submit" className="login-btn">로그인</button>
          </form>

          <div className="login-footer">
            <span>계정이 없으신가요?</span>
            <button className="go-signup" onClick={onGoSignup}>회원가입</button>
          </div>
        </div>
      </div>
    </div>
  );
}