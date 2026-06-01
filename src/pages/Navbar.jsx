import "../components/Navbar.css";

const Taegeuk = () => (
  <svg width="28" height="28" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5"/>
    <path d="M50 8 A42 42 0 0 1 50 92 A21 21 0 0 1 50 50 A21 21 0 0 0 50 8Z" fill="#C0392B"/>
    <path d="M50 92 A42 42 0 0 1 50 8 A21 21 0 0 1 50 50 A21 21 0 0 0 50 92Z" fill="#1a3a6e"/>
    <circle cx="50" cy="29" r="10.5" fill="#C0392B"/>
    <circle cx="50" cy="71" r="10.5" fill="#1a3a6e"/>
    <line x1="22" y1="34" x2="78" y2="34" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5"/>
    <line x1="22" y1="42" x2="78" y2="42" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5"/>
    <line x1="22" y1="58" x2="78" y2="58" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5"/>
    <line x1="22" y1="66" x2="78" y2="66" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5"/>
  </svg>
);

export default function Navbar({ isLoggedIn, onLogin, onLogout, onMypage, onHome }) {
  return (
    <nav className="navbar">
      <div className="nav-left" onClick={onHome} style={onHome ? { cursor: 'pointer' } : {}}>
        <Taegeuk />
        <span className="nav-logo">정책포털</span>
      </div>
      <div className="nav-right">
        {isLoggedIn ? (
          <>
            <button className="nav-btn" onClick={onMypage}>마이페이지</button>
            <button className="nav-btn" onClick={onLogout}>로그아웃</button>
          </>
        ) : (
          <button className="nav-btn" onClick={onLogin}>로그인</button>
        )}
      </div>
    </nav>
  );
}