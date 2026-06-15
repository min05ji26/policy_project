import { useState, useEffect } from "react";
import HomePage from "./pages/HomePage";
import ChatPage from "./pages/ChatPage";
import ResultPage from "./pages/ResultPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import MyPage from "./pages/MyPage";


export default function App() {
  const [page, setPage]           = useState("home");
  const [result, setResult]       = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser]           = useState(null);

  // 앱 시작 시 토큰으로 자동 로그인 복원
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    fetch(`/auth/me`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        setUser(data);
        setIsLoggedIn(true);
      })
      .catch(() => {
        localStorage.removeItem("token");
      });
  }, []);

  const handleLogin = (userData) => {
    setIsLoggedIn(true);
    setUser(userData);
    setPage("home");
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setIsLoggedIn(false);
    setUser(null);
    setPage("home");
  };

  return (
    <>
      {page === "home" && (
        <HomePage
          onStart={() => setPage("chat")}
          onLogin={() => setPage("login")}
          onLogout={handleLogout}
          onMypage={() => setPage("mypage")}
          isLoggedIn={isLoggedIn}
        />
      )}
      {page === "chat" && (
        <ChatPage
          onResult={(r) => { setResult(r); setPage("result"); }}
          onHome={() => setPage("home")}
          isLoggedIn={isLoggedIn}
          onLogout={handleLogout}
          onMypage={() => setPage("mypage")}
        />
      )}
      {page === "result" && (
        <ResultPage
          result={result}
          onReset={() => setPage("chat")}
          onHome={() => setPage("home")}
        />
      )}
      {page === "login" && (
        <LoginPage
          onLogin={handleLogin}
          onGoSignup={() => setPage("signup")}
          onHome={() => setPage("home")}
        />
      )}
      {page === "signup" && (
        <SignupPage
          onGoLogin={() => setPage("login")}
          onHome={() => setPage("home")}
          onSignupComplete={(userData) => {
            setUser(userData);
            setIsLoggedIn(true);
          }}
        />
      )}
      {page === "mypage" && (
        <MyPage
          user={user}
          onLogout={handleLogout}
          onHome={() => setPage("home")}
        />
      )}
    </>
  );
}
