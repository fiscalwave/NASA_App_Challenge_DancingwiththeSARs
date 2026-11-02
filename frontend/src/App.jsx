import { useState, Suspense } from 'react'
import Header from './components/Header'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <Suspense fallback={<div className="flex-1 flex items-center justify-center">Loading...</div>}>
        <Dashboard />
      </Suspense>
    </div>
  )
}
