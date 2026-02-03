import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

const CodeViewer = ({ jobId, onClose }) => {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    fetchGeneratedFiles();
  }, [jobId]);

  const fetchGeneratedFiles = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/generated-files`);
      if (!response.ok) throw new Error('Failed to fetch files');
      const data = await response.json();
      setFiles(data.files);
      if (data.files.length > 0) {
        setSelectedFile(data.files[0]);
      }
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const copyToClipboard = (content, fileId) => {
    navigator.clipboard.writeText(content);
    setCopiedId(fileId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const downloadFile = (file) => {
    const blob = new Blob([file.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadAllFiles = () => {
    files.forEach(file => {
      setTimeout(() => downloadFile(file), 100 * files.indexOf(file));
    });
  };

  const getLanguageColor = (language) => {
    const colors = {
      python: 'bg-blue-600 text-blue-100',
      javascript: 'bg-yellow-600 text-yellow-100',
      typescript: 'bg-blue-500 text-blue-100',
      bash: 'bg-green-600 text-green-100',
      json: 'bg-purple-600 text-purple-100',
      txt: 'bg-slate-600 text-slate-200'
    };
    return colors[language?.toLowerCase()] || 'bg-slate-600 text-slate-200';
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
        <div className="bg-slate-800 rounded-xl p-8 border border-slate-700">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto"></div>
          <p className="mt-4 text-slate-300">Loading generated files...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
        <div className="bg-slate-800 rounded-xl p-8 max-w-md border border-slate-700">
          <h3 className="text-xl font-bold text-red-400 mb-4">Error</h3>
          <p className="text-slate-300 mb-4">{error}</p>
          <button
            onClick={onClose}
            className="w-full bg-slate-700 text-white px-4 py-2 rounded-lg hover:bg-slate-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
        <div className="bg-slate-800 rounded-xl p-8 max-w-md border border-slate-700">
          <h3 className="text-xl font-bold text-white mb-4">No Generated Files</h3>
          <p className="text-slate-300 mb-4">This job didn't generate any code files.</p>
          <button
            onClick={onClose}
            className="w-full bg-slate-700 text-white px-4 py-2 rounded-lg hover:bg-slate-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col border border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div>
            <h2 className="text-2xl font-bold text-white">Generated Code</h2>
            <p className="text-sm text-slate-400">Job #{jobId} • {files.length} files</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={downloadAllFiles}
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-500 transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download All
            </button>
            <button
              onClick={onClose}
              className="bg-slate-700 text-white px-4 py-2 rounded-lg hover:bg-slate-600 transition-colors"
            >
              Close
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* File List */}
          <div className="w-64 border-r border-slate-700 overflow-y-auto bg-slate-850">
            <div className="p-3 border-b border-slate-700 bg-slate-750">
              <h3 className="font-semibold text-sm text-slate-300">Files</h3>
            </div>
            {files.map((file) => (
              <button
                key={file.id}
                onClick={() => setSelectedFile(file)}
                className={`w-full text-left p-3 border-b border-slate-700 hover:bg-slate-700 transition-colors ${
                  selectedFile?.id === file.id ? 'bg-slate-700 border-l-4 border-l-blue-500' : ''
                }`}
              >
                <div className="font-mono text-sm text-white truncate">{file.filename}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getLanguageColor(file.language)}`}>
                    {file.language || 'txt'}
                  </span>
                  <span className="text-xs text-slate-400">{(file.file_size / 1024).toFixed(1)} KB</span>
                </div>
              </button>
            ))}
          </div>

          {/* Code Preview */}
          {selectedFile && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex items-center justify-between p-3 border-b border-slate-700 bg-slate-750">
                <div>
                  <h3 className="font-mono font-semibold text-white">{selectedFile.filename}</h3>
                  <p className="text-sm text-slate-400">
                    {selectedFile.language} • {selectedFile.file_size} bytes
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => copyToClipboard(selectedFile.content, selectedFile.id)}
                    className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-500 transition-colors flex items-center gap-2"
                  >
                    {copiedId === selectedFile.id ? (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Copied!
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                        </svg>
                        Copy
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => downloadFile(selectedFile)}
                    className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-green-500 transition-colors flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto bg-slate-900 p-4">
                <pre className="text-sm">
                  <code className="text-slate-100 font-mono whitespace-pre-wrap break-words">
                    {selectedFile.content}
                  </code>
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CodeViewer;
