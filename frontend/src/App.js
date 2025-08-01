import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import SearchPage from './components/SearchPage';
import RealTimeSearch from './components/RealTimeSearch';
import DatabaseViewer from './components/DatabaseViewer';
import Header from './components/Header';
import Footer from './components/Footer';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Header />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<RealTimeSearch />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/hybrid" element={<RealTimeSearch />} />
            <Route path="/database" element={<DatabaseViewer />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
