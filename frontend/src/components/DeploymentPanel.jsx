import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

function DeploymentPanel({ jobId, jobStatus, onRefreshLogs }) {
  const [deployment, setDeployment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (jobStatus === 'completed') {
      checkStatus();
      const interval = setInterval(checkStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [jobId, jobStatus]);

  const checkStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/deployment`);
      if (response.ok) {
        const data = await response.json();
        setDeployment(data);
        
        if (onRefreshLogs && (data.deploy_requested || data.deployed)) {
          onRefreshLogs();
        }
        
        if (data.deployed || data.error) {
          setLoading(false);
        }
      }
    } catch (err) {
      console.error('Status check failed:', err);
    }
  };

  const requestDeployment = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/deploy`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Deployment failed');
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const stopDeployment = async () => {
    if (!window.confirm('Stop and cleanup deployment?')) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/deployment`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        throw new Error('Failed to stop deployment');
      }
      
      setDeployment(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Build deployment URL using current hostname (for network access)
  const getDeploymentUrl = () => {
    if (!deployment?.port) return null;
    return `http://${window.location.hostname}:${deployment.port}`;
  };

  if (jobStatus !== 'completed') return null;

  const isDeploying = loading || (deployment?.deploy_requested && !deployment?.deployed && !deployment?.error);
  const isRunning = deployment?.deployed;
  const hasError = deployment?.error;

  return (
    <div className="bg-slate-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-slate-300">Local Deployment</h4>
        {isRunning && (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            Running
          </span>
        )}
        {isDeploying && (
          <span className="flex items-center gap-1.5 text-xs text-blue-400">
            <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Deploying...
          </span>
        )}
      </div>

      {/* Idle state - show deploy button */}
      {!isRunning && !isDeploying && !hasError && (
        <button
          onClick={requestDeployment}
          disabled={loading}
          className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Deploy Locally
        </button>
      )}

      {/* Deploying state */}
      {isDeploying && (
        <div className="text-xs text-slate-400 space-y-1">
          <p>Writing files, installing dependencies...</p>
        </div>
      )}

      {/* Running state */}
      {isRunning && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 p-2 bg-slate-800 rounded-lg">
            <span className="text-slate-400 text-xs">URL:</span>
            <a 
              href={getDeploymentUrl()} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 text-sm font-mono flex-1 truncate"
            >
              {getDeploymentUrl()}
            </a>
            <button
              onClick={() => window.open(getDeploymentUrl(), '_blank')}
              className="px-2 py-1 bg-slate-600 hover:bg-slate-500 text-white text-xs rounded transition-colors"
            >
              Open
            </button>
          </div>
          
          <div className="flex gap-4 text-xs text-slate-500">
            <span>Port: {deployment.port}</span>
            <span>PID: {deployment.pid}</span>
            <span className="capitalize">{deployment.type}</span>
          </div>
          
          <button
            onClick={stopDeployment}
            className="w-full py-1.5 px-3 bg-red-600/20 hover:bg-red-600/30 text-red-400 text-xs font-medium rounded transition-colors"
          >
            Stop & Cleanup
          </button>
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <div className="space-y-2">
          <div className="p-2 bg-red-900/30 border border-red-700/50 rounded text-xs text-red-300 font-mono">
            {deployment.error}
          </div>
          <button
            onClick={requestDeployment}
            className="w-full py-1.5 px-3 bg-slate-600 hover:bg-slate-500 text-white text-xs font-medium rounded transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* General error banner */}
      {error && !hasError && (
        <div className="mt-2 p-2 bg-yellow-900/30 border border-yellow-700/50 rounded text-xs text-yellow-300 flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-yellow-400 hover:text-yellow-200">×</button>
        </div>
      )}
    </div>
  );
}

export default DeploymentPanel;
