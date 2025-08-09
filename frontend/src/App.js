import React from 'react';
import MainApp from './components/MainApp';
import Header from './components/Header';
import Footer from './components/Footer';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      <MainApp />
      <Footer />
    </div>
  );
}

export default App;
