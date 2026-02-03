import { useState, useEffect, useRef, useCallback } from 'react'
import CodeViewer from './components/CodeViewer'
import DeploymentPanel from './components/DeploymentPanel'
import { API_BASE_URL, WS_BASE_URL } from './config'

function App() {
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [showNewJobForm, setShowNewJobForm] = useState(false)
  const [selectedJobForCode, setSelectedJobForCode] = useState(null)
  const [newJob, setNewJob] = useState({
    title: '',
    description: '',
    ai_provider: 'auto',
    project_path: null
  })
  const [logs, setLogs] = useState([])
  const [wsStatus, setWsStatus] = useState('disconnected') // 'connected', 'disconnected', 'reconnecting'
  
  const wsRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 10
  const logsEndRef = useRef(null)
  const logsContainerRef = useRef(null)
  const userScrolledUp = useRef(false)
  const selectedJobRef = useRef(null)

  // Keep ref in sync with state for WebSocket handler
  useEffect(() => {
    selectedJobRef.current = selectedJob
  }, [selectedJob])

  // Fetch logs for selected job
  const fetchLogs = useCallback(async (jobId) => {
    if (!jobId) return
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/logs`)
      const data = await response.json()
      setLogs(data.reverse()) // Show oldest first
    } catch (error) {
      console.error('Error fetching logs:', error)
    }
  }, [])

  // Refresh selected job details
  const refreshSelectedJob = useCallback(async (jobId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`)
      const data = await response.json()
      setSelectedJob(data)
    } catch (error) {
      console.error('Error refreshing job:', error)
    }
  }, [])

  // Auto-scroll logs to bottom - only if user hasn't scrolled up
  useEffect(() => {
    if (logsEndRef.current && logsContainerRef.current && !userScrolledUp.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  // Reset scroll tracking when job changes
  useEffect(() => {
    userScrolledUp.current = false
  }, [selectedJob?.id])

  // Track if user scrolls up in the logs
  const handleLogsScroll = (e) => {
    const container = e.target
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 50
    userScrolledUp.current = !isNearBottom
  }

  // Fetch logs when selected job changes
  useEffect(() => {
    if (selectedJob?.id) {
      fetchLogs(selectedJob.id)
    } else {
      setLogs([])
    }
  }, [selectedJob?.id, fetchLogs])

  // WebSocket connection with reconnection logic
  useEffect(() => {
    let reconnectTimeout = null
    let pingInterval = null

    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return

      setWsStatus('reconnecting')
      const websocket = new WebSocket(`${WS_BASE_URL}/ws`)
      
      websocket.onopen = () => {
        console.log('WebSocket connected')
        setWsStatus('connected')
        reconnectAttempts.current = 0
        
        // Start heartbeat ping every 30 seconds
        pingInterval = setInterval(() => {
          if (websocket.readyState === WebSocket.OPEN) {
            websocket.send('ping')
          }
        }, 30000)
      }
      
      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'job_update' || data.type === 'job_created' || data.type === 'job_cancelled') {
            fetchJobs()
          }
          if (data.type === 'log_update' && data.job_id === selectedJobRef.current?.id) {
            fetchLogs(data.job_id)
          }
          // Also refresh logs and job details when status changes for selected job
          if (data.type === 'job_update' && data.job_id === selectedJobRef.current?.id) {
            fetchLogs(data.job_id)
            // Refresh selected job details
            refreshSelectedJob(data.job_id)
          }
        } catch (e) {
          // Ignore non-JSON messages (like pong)
        }
      }
      
      websocket.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      websocket.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        setWsStatus('disconnected')
        clearInterval(pingInterval)
        
        // Attempt reconnection with exponential backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1})`)
          reconnectTimeout = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        } else {
          console.error('Max reconnection attempts reached')
        }
      }
      
      wsRef.current = websocket
    }

    connect()
    fetchJobs()

    // Cleanup on unmount
    return () => {
      clearTimeout(reconnectTimeout)
      clearInterval(pingInterval)
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchJobs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs`)
      const data = await response.json()
      setJobs(data)
    } catch (error) {
      console.error('Error fetching jobs:', error)
    }
  }

  const createJob = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newJob)
      })
      
      if (response.ok) {
        setNewJob({ title: '', description: '', ai_provider: 'auto', project_path: null })
        setShowNewJobForm(false)
        fetchJobs()
      }
    } catch (error) {
      console.error('Error creating job:', error)
    }
  }

  // Stats calculations
  const stats = {
    total: jobs.length,
    queued: jobs.filter(j => j.status === 'queued').length,
    running: jobs.filter(j => ['planning', 'building', 'testing', 'sandboxing'].includes(j.status)).length,
    completed: jobs.filter(j => j.status === 'completed').length,
    failed: jobs.filter(j => j.status === 'failed').length
  }

  const getStatusColor = (status) => {
    const colors = {
      queued: 'bg-slate-600 text-slate-200',
      planning: 'bg-blue-600 text-blue-100',
      building: 'bg-yellow-600 text-yellow-100',
      testing: 'bg-purple-600 text-purple-100',
      sandboxing: 'bg-indigo-600 text-indigo-100',
      completed: 'bg-green-600 text-green-100',
      failed: 'bg-red-600 text-red-100'
    }
    return colors[status] || 'bg-slate-600 text-slate-200'
  }

  const getStatusIcon = (status) => {
    switch(status) {
      case 'completed':
        return '✅'
      case 'failed':
        return '❌'
      case 'queued':
        return '⏳'
      case 'planning':
        return '📋'
      case 'building':
        return '🔨'
      case 'testing':
        return '🧪'
      case 'sandboxing':
        return '📦'
      default:
        return '🔄'
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Vitso Dev Orchestrator</h1>
                <p className="text-sm text-slate-400">AI-Powered Development Pipeline</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {/* WebSocket Status Indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 rounded-lg">
                <div className={`w-2 h-2 rounded-full ${{
                  connected: 'bg-green-500',
                  disconnected: 'bg-red-500',
                  reconnecting: 'bg-yellow-500 animate-pulse'
                }[wsStatus]}`} />
                <span className="text-xs text-slate-400 capitalize">{wsStatus}</span>
              </div>
              
              <button
                onClick={() => setShowNewJobForm(true)}
                className="bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 px-5 rounded-lg transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                New Job
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Stats Cards */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-3xl font-bold text-white">{stats.total}</p>
                <p className="text-sm text-slate-400 mt-1">Total Jobs</p>
              </div>
              <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
          </div>
          
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-3xl font-bold text-white">{stats.queued}</p>
                <p className="text-sm text-slate-400 mt-1">Queued</p>
              </div>
              <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-3xl font-bold text-white">{stats.running}</p>
                <p className="text-sm text-slate-400 mt-1">Running</p>
              </div>
              <svg className="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-3xl font-bold text-green-400">{stats.completed}</p>
                <p className="text-sm text-slate-400 mt-1">Completed</p>
              </div>
              <svg className="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-3xl font-bold text-red-400">{stats.failed}</p>
                <p className="text-sm text-slate-400 mt-1">Failed</p>
              </div>
              <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content - Split Panel */}
      <main className="max-w-7xl mx-auto px-6 pb-8">
        <div className="grid grid-cols-2 gap-6 h-[calc(100vh-280px)]">
          {/* Left Panel - Job List */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-slate-700">
              <h2 className="text-lg font-semibold text-white">Recent Jobs</h2>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500">
                  <svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p>No jobs yet</p>
                  <p className="text-sm mt-1">Click "New Job" to get started</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-700">
                  {jobs.map((job) => (
                    <div
                      key={job.id}
                      onClick={() => setSelectedJob(job)}
                      className={`px-5 py-4 cursor-pointer transition-colors ${
                        selectedJob?.id === job.id
                          ? 'bg-slate-700'
                          : 'hover:bg-slate-750 hover:bg-opacity-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{getStatusIcon(job.status)}</span>
                            <h3 className="font-medium text-white truncate">{job.title}</h3>
                          </div>
                          <p className="text-sm text-slate-400 mt-1 truncate">{job.description}</p>
                          <p className="text-xs text-slate-500 mt-1">
                            Job #{job.id} • {new Date(job.created_at).toLocaleString()}
                          </p>
                        </div>
                        <span className={`ml-3 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}>
                          {job.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Job Details */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex flex-col">
            {selectedJob ? (
              <>
                <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-white">Job Details</h2>
                  {selectedJob.status === 'completed' && (
                    <button
                      onClick={() => setSelectedJobForCode(selectedJob.id)}
                      className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                      </svg>
                      View Code
                    </button>
                  )}
                </div>
                
                <div className="flex-1 overflow-y-auto p-5">
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-2xl font-bold text-white">{selectedJob.title}</h3>
                      <span className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(selectedJob.status)}`}>
                        {getStatusIcon(selectedJob.status)} {selectedJob.status.toUpperCase()}
                      </span>
                    </div>
                    
                    <div className="bg-slate-700 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-slate-300 mb-2">Description</h4>
                      <p className="text-slate-200">{selectedJob.description}</p>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-slate-300 mb-1">Job ID</h4>
                        <p className="text-white font-mono">#{selectedJob.id}</p>
                      </div>
                      <div className="bg-slate-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-slate-300 mb-1">AI Provider</h4>
                        <p className="text-white capitalize">{selectedJob.ai_provider}</p>
                      </div>
                      <div className="bg-slate-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-slate-300 mb-1">Created</h4>
                        <p className="text-white text-sm">{new Date(selectedJob.created_at).toLocaleString()}</p>
                      </div>
                      <div className="bg-slate-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-slate-300 mb-1">Completed</h4>
                        <p className="text-white text-sm">
                          {selectedJob.completed_at 
                            ? new Date(selectedJob.completed_at).toLocaleString()
                            : '—'
                          }
                        </p>
                      </div>
                    </div>
                    
                    {/* Token & Time Tracking */}
                    {(selectedJob.total_tokens > 0 || selectedJob.execution_time_seconds > 0) && (
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-slate-700 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-slate-300 mb-1">Tokens Used</h4>
                          <p className="text-white font-mono text-lg">
                            {selectedJob.total_tokens?.toLocaleString() || '—'}
                          </p>
                        </div>
                        <div className="bg-slate-700 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-slate-300 mb-1">Execution Time</h4>
                          <p className="text-white font-mono text-lg">
                            {selectedJob.execution_time_seconds 
                              ? `${Math.floor(selectedJob.execution_time_seconds / 60)}m ${selectedJob.execution_time_seconds % 60}s`
                              : '—'
                            }
                          </p>
                        </div>
                        <div className="bg-slate-700 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-slate-300 mb-1">Est. Cost</h4>
                          <p className="text-green-400 font-mono text-lg">
                            {selectedJob.estimated_cost || '—'}
                          </p>
                        </div>
                      </div>
                    )}
                    
                    {selectedJob.error_message && (
                      <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-red-400 mb-2">Error</h4>
                        <p className="text-red-200 text-sm font-mono">{selectedJob.error_message}</p>
                      </div>
                    )}

                    {/* GitHub Repository Link */}
                    {selectedJob.github_repo_url && (
                      <div className="bg-slate-700 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-slate-300 mb-2">GitHub Repository</h4>
                        <div className="flex items-center gap-3">
                          <svg className="w-6 h-6 text-slate-400" fill="currentColor" viewBox="0 0 24 24">
                            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                          </svg>
                          <div className="flex-1">
                            <a 
                              href={selectedJob.github_repo_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
                            >
                              {selectedJob.github_repo_name || selectedJob.github_repo_url}
                            </a>
                            {selectedJob.github_pushed_at && (
                              <p className="text-xs text-slate-500 mt-1">
                                Pushed {new Date(selectedJob.github_pushed_at).toLocaleString()}
                              </p>
                            )}
                          </div>
                          <a
                            href={selectedJob.github_repo_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-sm transition-colors"
                          >
                            Open
                          </a>
                        </div>
                      </div>
                    )}

                    {/* Pipeline Progress */}
                    <div className="bg-slate-700 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-slate-300 mb-3">Pipeline Progress</h4>
                      <div className="relative">
                        {/* Background line */}
                        <div className="absolute top-4 left-4 right-4 h-1 bg-slate-600" />
                        {/* Progress line */}
                        {(() => {
                          const stageOrder = ['queued', 'planning', 'building', 'testing', 'sandboxing', 'completed']
                          const currentIdx = stageOrder.indexOf(selectedJob.status)
                          const progressPercent = selectedJob.status === 'failed' ? 0 : Math.max(0, (currentIdx - 1) / 4) * 100
                          return (
                            <div 
                              className="absolute top-4 left-4 h-1 bg-green-600 transition-all duration-300" 
                              style={{ width: `calc(${progressPercent}% - ${progressPercent > 0 ? '16px' : '0px'})` }}
                            />
                          )
                        })()}
                        {/* Circles and labels */}
                        <div className="relative flex items-center justify-between">
                          {['planning', 'building', 'testing', 'sandboxing', 'completed'].map((stage, idx) => {
                            const stageOrder = ['queued', 'planning', 'building', 'testing', 'sandboxing', 'completed']
                            const stageLabels = ['Plan', 'Build', 'Test', 'Sandbox', 'Done']
                            const currentIdx = stageOrder.indexOf(selectedJob.status)
                            const stageIdx = stageOrder.indexOf(stage)
                            const isComplete = currentIdx > stageIdx || selectedJob.status === stage
                            const isCurrent = selectedJob.status === stage
                            const isFailed = selectedJob.status === 'failed'
                            
                            return (
                              <div key={stage} className="flex flex-col items-center">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${
                                  isFailed ? 'bg-red-600 text-white' :
                                  isComplete ? 'bg-green-600 text-white' :
                                  isCurrent ? 'bg-blue-600 text-white animate-pulse' :
                                  'bg-slate-600 text-slate-400'
                                }`}>
                                  {idx + 1}
                                </div>
                                <span className="text-xs text-slate-400 mt-2">{stageLabels[idx]}</span>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </div>

                    {/* Job Logs */}
                    <div className="bg-slate-700 rounded-lg p-4">
                      <div className="flex justify-between items-center mb-3">
                        <h4 className="text-sm font-medium text-slate-300">Job Logs</h4>
                        <button
                          onClick={() => fetchLogs(selectedJob.id)}
                          className="text-xs text-slate-400 hover:text-white transition-colors flex items-center gap-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                          Refresh
                        </button>
                      </div>
                      <div 
                        ref={logsContainerRef}
                        onScroll={handleLogsScroll}
                        className="bg-slate-900 rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs"
                      >
                        {logs.length === 0 ? (
                          <div className="flex items-center justify-center h-full text-slate-500">
                            <p>No logs yet</p>
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {logs.map((log) => (
                              <div key={log.id} className="flex gap-2">
                                <span className="text-slate-500 shrink-0">
                                  {new Date(log.timestamp).toLocaleTimeString()}
                                </span>
                                <span className={`shrink-0 px-1.5 rounded text-xs ${
                                  log.level === 'error' ? 'bg-red-900/50 text-red-400' :
                                  log.level === 'warning' ? 'bg-yellow-900/50 text-yellow-400' :
                                  log.level === 'success' ? 'bg-green-900/50 text-green-400' :
                                  'bg-slate-800 text-slate-400'
                                }`}>
                                  {log.level.toUpperCase()}
                                </span>
                                <span className="text-slate-300 break-all">{log.message}</span>
                              </div>
                            ))}
                            <div ref={logsEndRef} />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Deployment Panel */}
                    {selectedJob.status === 'completed' && (
                      <DeploymentPanel 
                        jobId={selectedJob.id} 
                        jobStatus={selectedJob.status}
                        onRefreshLogs={() => fetchLogs(selectedJob.id)}
                      />
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <p>Select a job to view details</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* New Job Modal */}
      {showNewJobForm && (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl shadow-2xl p-6 w-full max-w-2xl border border-slate-700">
            <h2 className="text-2xl font-bold text-white mb-4">Create New Job</h2>
            <form onSubmit={createJob}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    Job Title
                  </label>
                  <input
                    type="text"
                    required
                    value={newJob.title}
                    onChange={(e) => setNewJob({...newJob, title: e.target.value})}
                    className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="e.g., Build a REST API for user management"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    Job Description
                  </label>
                  <textarea
                    required
                    value={newJob.description}
                    onChange={(e) => setNewJob({...newJob, description: e.target.value})}
                    rows={6}
                    className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Describe what you want to build in detail..."
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    AI Provider
                  </label>
                  <select
                    value={newJob.ai_provider}
                    onChange={(e) => setNewJob({...newJob, ai_provider: e.target.value})}
                    className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="auto">Auto (Recommended)</option>
                    <option value="claude">Claude</option>
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                  </select>
                </div>

                <div className="flex items-center gap-3 p-4 bg-slate-700/50 rounded-lg border border-slate-600">
                  <input
                    type="checkbox"
                    id="scanCodebase"
                    checked={newJob.project_path === '/app'}
                    onChange={(e) => setNewJob({...newJob, project_path: e.target.checked ? '/app' : null})}
                    className="w-5 h-5 rounded border-slate-500 bg-slate-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-slate-800"
                  />
                  <div>
                    <label htmlFor="scanCodebase" className="text-sm font-medium text-slate-300 cursor-pointer">
                      Scan VDO codebase for context
                    </label>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Enable this for self-improvement jobs. VDO will analyze its own code to generate better, targeted tasks.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowNewJobForm(false)}
                  className="px-5 py-2.5 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors font-medium"
                >
                  Create & Start Job
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Code Viewer Modal */}
      {selectedJobForCode && (
        <CodeViewer
          jobId={selectedJobForCode}
          onClose={() => setSelectedJobForCode(null)}
        />
      )}
    </div>
  )
}

export default App
