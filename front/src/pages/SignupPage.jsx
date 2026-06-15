import { useState } from "react";
import Navbar from "./Navbar";
import "../components/SignupPage.css";


export default function SignupPage({ onGoLogin, onHome, onSignupComplete }) {
  const [form, setForm] = useState({
    name: "", email: "", password: "", passwordConfirm: "",
    birthYear: "", gender: "",
  });
  const [error, setError]   = useState("");
  const [done, setDone]     = useState(false);
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.name || !form.email || !form.password || !form.birthYear || !form.gender) {
      setError("모든 항목을 입력해주세요."); return;
    }
    if (form.password !== form.passwordConfirm) { setError("비밀번호가 일치하지 않아요."); return; }
    if (form.password.length < 8) { setError("비밀번호는 8자 이상이어야 해요."); return; }
    const year = parseInt(form.birthYear);
    if (isNaN(year) || year < 1900 || year > new Date().getFullYear()) {
      setError("올바른 출생연도를 입력해주세요."); return;
    }

    setLoading(true);
    try {
      const res = await fetch(`/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email:      form.email,
          password:   form.password,
          name:       form.name,
          birth_year: year,
          gender:     form.gender,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "회원가입 실패"); return; }

      localStorage.setItem("token", data.access_token);
      if (onSignupComplete) onSignupComplete(data.user);
      setDone(true);
    } catch (err) {
      setError("서버 연결에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
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

          <div className="social-section">
            <button className="social-btn kakao" onClick={() => alert("카카오 로그인은 배포 환경에서 이용 가능해요.")}>
              <svg width="20" height="20" viewBox="0 0 18 18" fill="none">
                <path d="M9 1.5C4.86 1.5 1.5 4.09 1.5 7.27c0 2.03 1.35 3.81 3.38 4.83l-.86 3.2 3.74-2.46c.4.06.81.09 1.24.09 4.14 0 7.5-2.59 7.5-5.77S13.14 1.5 9 1.5z" fill="#3C1E1E"/>
              </svg>
              카카오로 시작하기
            </button>
          </div>

          <div className="divider"><span>이메일로 가입</span></div>

          <form onSubmit={handleSignup} className="signup-form">
            <div className="field">
              <label>이름</label>
              <input type="text" placeholder="실명 입력" value={form.name}
                onChange={e => set("name", e.target.value)} disabled={loading} />
            </div>
            <div className="field">
              <label>출생연도</label>
              <input type="number" placeholder="예: 1998" min="1900" max={new Date().getFullYear()}
                value={form.birthYear} onChange={e => set("birthYear", e.target.value)} disabled={loading} />
            </div>
            <div className="field">
              <label>성별</label>
              <select value={form.gender} onChange={e => set("gender", e.target.value)} disabled={loading}>
                <option value="">선택하세요</option>
                <option value="male">남성</option>
                <option value="female">여성</option>
                <option value="other">기타</option>
              </select>
            </div>
            <div className="field">
              <label>이메일</label>
              <input type="email" placeholder="example@email.com" value={form.email}
                onChange={e => set("email", e.target.value)} disabled={loading} />
            </div>
            <div className="field">
              <label>비밀번호</label>
              <input type="password" placeholder="8자 이상" value={form.password}
                onChange={e => set("password", e.target.value)} disabled={loading} />
            </div>
            <div className="field">
              <label>비밀번호 확인</label>
              <input type="password" placeholder="비밀번호 재입력" value={form.passwordConfirm}
                onChange={e => set("passwordConfirm", e.target.value)} disabled={loading} />
            </div>
            {error && <p className="error-msg">{error}</p>}
            <button type="submit" className="signup-submit" disabled={loading}>
              {loading ? "가입 중..." : "가입하기"}
            </button>
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
