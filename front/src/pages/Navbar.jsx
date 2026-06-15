import { useNavigate } from "react-router-dom";
import "../components/Navbar.css";

import TaegeukgiImg from "../assets/taegeukgi.png";

export default function Navbar({ isLoggedIn, onLogin, onLogout, onMypage, onHome }) {
  return (
    <nav className="navbar">
      <div className="nav-left" onClick={onHome}>
        <img src={TaegeukgiImg} alt="태극기" style={{ width: 57, height: 60, objectFit: "contain" }} />
        <span className="nav-logo">청년 정책 사이트</span>
      </div>

      <div className="nav-right">
        {isLoggedIn ? (
          <>
            <button className="nav-btn" onClick={onMypage}>마이페이지</button>
            <button className="nav-btn nav-btn-primary" onClick={onLogout}>로그아웃</button>
          </>
        ) : (
          <button className="nav-btn-login" onClick={onLogin}>로그인 / 회원가입</button>
        )}
      </div>
    </nav>
  );
}
