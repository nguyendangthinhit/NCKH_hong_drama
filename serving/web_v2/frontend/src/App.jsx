import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Header from './components/Header/Header';
import Footer from './components/Footer/Footer';
import HomePage from './pages/HomePage/HomePage';
import FacebookPage from './pages/FacebookPage/FacebookPage';
import NewsPage from './pages/NewsPage/NewsPage';
import ChatPage from './pages/ChatPage/ChatPage';
import Chatbot from './components/Chatbot/Chatbot';
import { ChatHistoryProvider } from './context/ChatHistoryContext';

function Layout() {
  // Trang chat chiếm trọn màn hình nên không hiện footer.
  const isChatPage = useLocation().pathname.startsWith('/chat');

  return (
    <>
      <Header />

      <Routes>
        <Route path="/"         element={<HomePage />} />
        <Route path="/facebook" element={<FacebookPage />} />
        <Route path="/news"     element={<NewsPage />} />
        <Route path="/chat"     element={<ChatPage />} />
      </Routes>
      <Chatbot />
      {!isChatPage && <Footer />}
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ChatHistoryProvider>
        <Layout />
      </ChatHistoryProvider>
    </BrowserRouter>
  );
}

export default App;
