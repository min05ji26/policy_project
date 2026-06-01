import { useState } from 'react'
import Homepage from './pages/Homepage'
import ChatPage from './pages/ChatPage'
import ResultPage from './pages/ResultPage'

function App() {
  const [page, setPage] = useState('home')
  const [result, setResult] = useState(null)

  if (page === 'chat') {
    return (
      <ChatPage
        onResult={(r) => { setResult(r); setPage('result') }}
        onHome={() => setPage('home')}
      />
    )
  }

  if (page === 'result') {
    return (
      <ResultPage
        result={result}
        onReset={() => setPage('home')}
        onHome={() => setPage('home')}
      />
    )
  }

  return <Homepage onStart={() => setPage('chat')} />
}

export default App
