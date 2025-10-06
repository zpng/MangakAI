import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AsyncMangaGenerator from './AsyncMangaGenerator.jsx';

const AppRouter = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="/home" element={<AsyncMangaGenerator />} />
      <Route path="/upload" element={<AsyncMangaGenerator />} />
      <Route path="/regenerate" element={<AsyncMangaGenerator />} />
      <Route path="/histories" element={<AsyncMangaGenerator />} />
      <Route path="/examples" element={<AsyncMangaGenerator />} />
    </Routes>
  );
};

export default AppRouter;