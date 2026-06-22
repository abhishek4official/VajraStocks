import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, RefreshCw, Trash2, AlertTriangle, CheckCircle, Clock, XCircle, FileText } from 'lucide-react';
import { apiService } from '../services/api';
import type { EodImportJob } from '../services/api';

const ACTIVE_STATUSES = new Set([
  'PENDING', 'VALIDATING', 'STAGING', 'GAP_FILLING', 'PATCHING', 'CALCULATING', 'REFRESHING',
]);

const STATUS_LABEL: Record<string, string> = {
  PENDING:    'Queued',
  VALIDATING: 'Validating file…',
  STAGING:    'Staging data…',
  GAP_FILLING:'Filling gaps via Yahoo…',
  PATCHING:   'Patching missing symbols…',
  CALCULATING:'Calculating indicators…',
  REFRESHING: 'Refreshing screener…',
  SUCCESS:    'Complete',
  FAILED:     'Failed',
  DUPLICATE:  'Duplicate',
};

function StatusBadge({ status }: { status: string }) {
  const isActive = ACTIVE_STATUSES.has(status);
  const color =
    status === 'SUCCESS'   ? 'text-green-400 bg-green-500/10 border-green-500/30' :
    status === 'FAILED'    ? 'text-red-400 bg-red-500/10 border-red-500/30'       :
    status === 'DUPLICATE' ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30' :
    isActive               ? 'text-blue-400 bg-blue-500/10 border-blue-500/30'    :
                             'text-text-muted bg-bg-surface border-border-subtle';

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${color}`}>
      {isActive && <RefreshCw className="w-3 h-3 animate-spin" />}
      {status === 'SUCCESS'   && <CheckCircle className="w-3 h-3" />}
      {status === 'FAILED'    && <XCircle className="w-3 h-3" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function JobRow({ job, onDelete, onRetry }: { job: EodImportJob; onDelete: () => void; onRetry: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const isActive = ACTIVE_STATUSES.has(job.status);

  return (
    <div className="border border-border-subtle rounded-lg bg-bg-surface overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-bg-hover transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <FileText className="w-4 h-4 text-text-muted shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-text-main truncate">{job.filename}</p>
          <p className="text-xs text-text-muted">{job.file_date}</p>
        </div>
        <StatusBadge status={job.status} />
        {!isActive && (
          <div className="flex gap-1" onClick={e => e.stopPropagation()}>
            {job.status === 'FAILED' && job.eod_patched_count != null && job.eod_patched_count > 0 && (
              <button
                onClick={onRetry}
                title="Retry calculations"
                className="p-1.5 rounded text-text-muted hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={onDelete}
              title="Delete job (allows re-import)"
              className="p-1.5 rounded text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {expanded && (
        <div className="border-t border-border-subtle px-4 py-3 text-xs space-y-2 bg-bg-base/40">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {[
              ['Total rows', job.total_rows],
              ['Equity rows', job.equity_rows],
              ['Staged', job.staged_count],
              ['Yahoo filled', job.yahoo_filled_count],
              ['EOD patched', job.eod_patched_count],
              ['Unresolved symbols', job.unresolved_symbols?.length ?? 0],
            ].map(([label, value]) => (
              <div key={String(label)} className="bg-bg-surface rounded p-2">
                <p className="text-text-muted">{label}</p>
                <p className="font-semibold text-text-main">{value ?? '—'}</p>
              </div>
            ))}
          </div>

          {job.gap_info && (job.gap_info.symbols_with_gap > 0 || job.gap_info.symbols_with_no_history > 0) && (
            <div className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded p-2 text-yellow-300">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold">Gap detected: </span>
                {job.gap_info.symbols_with_gap} symbols had missing days before {job.gap_info.file_date}
                {job.gap_info.symbols_with_no_history > 0 &&
                  ` · ${job.gap_info.symbols_with_no_history} with no prior history`}
                . Yahoo Finance sync was run to fill these automatically.
              </div>
            </div>
          )}

          {job.unresolved_symbols && job.unresolved_symbols.length > 0 && (
            <div className="bg-bg-surface rounded p-2">
              <p className="text-text-muted mb-1">Unresolved symbols ({job.unresolved_symbols.length})</p>
              <p className="text-text-main font-mono">{job.unresolved_symbols.slice(0, 10).join(', ')}
                {job.unresolved_symbols.length > 10 ? ` +${job.unresolved_symbols.length - 10} more` : ''}
              </p>
            </div>
          )}

          {job.error_message && (
            <div className="bg-red-500/10 border border-red-500/30 rounded p-2 text-red-300 font-mono">
              {job.error_message}
            </div>
          )}

          {job.completed_at && (
            <p className="text-text-muted">
              Completed: {new Date(job.completed_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export const EodImportPanel: React.FC = () => {
  const [jobs, setJobs] = useState<EodImportJob[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try { setJobs(await apiService.listEodJobs(30)); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 4000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [load]);

  const hasActive = jobs.some(j => ACTIVE_STATUSES.has(j.status));

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploadError('');
    setUploading(true);
    try {
      await apiService.uploadEodFile(file);
      await load();
    } catch (e: any) {
      setUploadError(e.message ?? 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDelete = async (jobId: string) => {
    try { await apiService.deleteEodJob(jobId); await load(); } catch { /* silent */ }
  };

  const handleRetry = async (jobId: string) => {
    try { await apiService.retryEodCalculations(jobId); await load(); } catch { /* silent */ }
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && fileRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-150
          ${isDragging
            ? 'border-accent-primary bg-accent-primary/5'
            : 'border-border-subtle hover:border-accent-primary/50 hover:bg-bg-surface/50'
          }
          ${uploading ? 'opacity-60 pointer-events-none' : ''}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2 text-text-muted">
            <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
            <p className="text-sm font-medium">Uploading…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-8 h-8 text-text-muted" />
            <p className="text-sm font-semibold text-text-main">
              Drop NSE Bhavcopy file here
            </p>
            <p className="text-xs text-text-muted">
              Format: <span className="font-mono text-accent-primary">PD{'{DDMMYYYY}'}.csv</span>
              &nbsp;· e.g. PD22062026.csv
            </p>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-300 text-sm">
          <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {uploadError}
        </div>
      )}

      {/* Info note */}
      <div className="flex items-start gap-2 bg-blue-500/5 border border-blue-500/20 rounded-lg px-4 py-3 text-xs text-blue-300">
        <Clock className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <strong>Yahoo-first strategy:</strong> After upload, Yahoo Finance syncs all data gaps
          automatically. EOD data is only used for symbols Yahoo cannot provide (e.g. same-day upload).
        </span>
      </div>

      {/* Job list */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
            Import History
          </h3>
          {hasActive && (
            <span className="text-xs text-blue-400 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" /> Processing…
            </span>
          )}
        </div>

        {jobs.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-6">No imports yet.</p>
        ) : (
          jobs.map(job => (
            <JobRow
              key={job.job_id}
              job={job}
              onDelete={() => handleDelete(job.job_id)}
              onRetry={() => handleRetry(job.job_id)}
            />
          ))
        )}
      </div>
    </div>
  );
};
