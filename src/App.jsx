import { useState } from "react";
import HomePage from "./pages/Homepage";
import ChatPage from "./pages/ChatPage";
import ResultPage from "./pages/ResultPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";

export default function App() {
  const [page, setPage] = useState("home");
  const [result, setResult] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  return (
    <>
      {page === "home" && (
        <HomePage
          onStart={() => setPage("chat")}
          onLogin={() => setPage("login")}
          isLoggedIn={isLoggedIn}
        />
      )}
      {page === "chat" && (
        <ChatPage
          onResult={(r) => { setResult(r); setPage("result"); }}
          onHome={() => setPage("home")}
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
          onLogin={() => { setIsLoggedIn(true); setPage("home"); }}
          onGoSignup={() => setPage("signup")}
          onHome={() => setPage("home")}
        />
      )}
      {page === "signup" && (
        <SignupPage
          onGoLogin={() => setPage("login")}
          onHome={() => setPage("home")}
        />
      )}
    </>
  );
}