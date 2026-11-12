// Точка входа SPA. Маршруты:
//   /demo        — выбор сценария и старт (демо-режим, DEMO_MODE=true на бэкенде)
//   /i/:token    — чат интервью и протокол в конце
//   /app/*       — кабинет рекрутера (в разработке)
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ChatPage from "./candidate/ChatPage";
import DemoPage from "./demo/DemoPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/i/:token" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/demo" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
