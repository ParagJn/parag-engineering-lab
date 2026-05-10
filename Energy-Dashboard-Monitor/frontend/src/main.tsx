import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DashboardLayout from './components/layout/DashboardLayout'
import PipelineOverview from './pages/PipelineOverview'
import RealTimeMonitor from './pages/RealTimeMonitor'
import DataQualityLab from './pages/DataQualityLab'
import LoadHistory from './pages/LoadHistory'
import './index.css'

// No more placeholders

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<PipelineOverview />} />
          <Route path="monitor" element={<RealTimeMonitor />} />
          <Route path="quality" element={<DataQualityLab />} />
          <Route path="history" element={<LoadHistory />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
