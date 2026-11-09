import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header/Header';
import Footer from './components/Footer/Footer';
import HomePage from './pages/HomePage/HomePage';
import FacebookPage from './pages/FacebookPage/FacebookPage';
import NewsPage from './pages/NewsPage/NewsPage';
import EventDetailPage from './pages/Event_detail/event-detail-page';
import EventsPage from './pages/EventsPage/events-page';
import Chatbot from './components/Chatbot/Chatbot';

function App() {
  return (
    <BrowserRouter>
      <Header />

      <Routes>
        <Route path="/"         element={<HomePage />} />
        <Route path="/facebook" element={<FacebookPage />} />
        <Route path="/news"     element={<NewsPage />} />
        <Route path="/events"   element={<EventsPage />} />
        <Route path="/events/:id" element={<EventDetailPage />} />
      </Routes>
      <Chatbot />
      <Footer />
    </BrowserRouter>
  );
}

export default App;

