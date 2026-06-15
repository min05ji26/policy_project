import Navbar from "./Navbar";
import "../components/MyPage.css";

export default function MyPage({ user, onLogout, onHome }) {
  const age = user?.birth_year
    ? new Date().getFullYear() - parseInt(user.birth_year)
    : null;

  const genderLabel = { male: "남성", female: "여성", other: "기타" }[user?.gender] || "-";
  const firstChar   = user?.name ? user.name[0] : "?";

  return (
    <div className="mypage-wrap">
      <Navbar
        isLoggedIn={true}
        onLogout={onLogout}
        onMypage={() => {}}
        onHome={onHome}
      />
      <div className="mypage-container">
        <div className="mypage-card">
          <h2 className="mypage-title">마이페이지</h2>

          <div className="mypage-profile-header">
            <div className="mypage-avatar">{firstChar}</div>
            <div className="mypage-name-section">
              <p className="mypage-display-name">{user?.name || "사용자"}</p>
              <span className={`mypage-login-badge ${user?.login_type === "kakao" ? "kakao" : "email"}`}>
                {user?.login_type === "kakao" ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
                      <path d="M9 1.5C4.86 1.5 1.5 4.09 1.5 7.27c0 2.03 1.35 3.81 3.38 4.83l-.86 3.2 3.74-2.46c.4.06.81.09 1.24.09 4.14 0 7.5-2.59 7.5-5.77S13.14 1.5 9 1.5z" fill="#3C1E1E"/>
                    </svg>
                    카카오 로그인
                  </>
                ) : (
                  <>✉ 이메일 로그인</>
                )}
              </span>
            </div>
          </div>

          <div className="mypage-info-list">
            <div className="mypage-info-row">
              <span className="mypage-info-label">이름</span>
              <span className="mypage-info-value">{user?.name || "-"}</span>
            </div>
            <div className="mypage-info-row">
              <span className="mypage-info-label">나이</span>
              <span className="mypage-info-value">
                {age ? `${age}세 (${user.birth_year}년생)` : "-"}
              </span>
            </div>
            <div className="mypage-info-row">
              <span className="mypage-info-label">성별</span>
              <span className="mypage-info-value">{genderLabel}</span>
            </div>
            <div className="mypage-info-row">
              <span className="mypage-info-label">이메일</span>
              <span className="mypage-info-value">{user?.email || "-"}</span>
            </div>
            <div className="mypage-info-row">
              <span className="mypage-info-label">가입 방식</span>
              <span className="mypage-info-value">
                {user?.login_type === "kakao" ? "카카오 계정" : "이메일 계정"}
              </span>
            </div>
          </div>

          <div className="mypage-actions">
            <button className="mypage-home-btn" onClick={onHome}>
              정책 찾으러 가기
            </button>
            <button className="mypage-logout-btn" onClick={onLogout}>
              로그아웃
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
