import React, { useEffect, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import { useSettingsCtx } from '../contexts/SettingsContext';
import { 
  RefreshCw, 
  Settings, 
  Cpu, 
  History, 
  Heart, 
  CheckCircle, 
  AlertOctagon,
  AlertTriangle 
} from 'lucide-react';

export const SyncPanel: React.FC = () => {
  const {
    syncJobs,
    syncStatuses,
    fetchSyncLogs,
    triggerFullSync,
    triggerRecalculate,
    isSyncing
  } = useStockStore();

  const { get } = useSettingsCtx();
  const pollIntervalMs = get('UI', 'sync_poll_interval_ms', 5000);

  const [activeSubTab, setActiveSubTab] = useState<'history' | 'status'>('history');

  useEffect(() => {
    fetchSyncLogs();
    // Poll interval driven by DB setting UI/sync_poll_interval_ms (default 5000 ms)
    const interval = setInterval(() => {
      fetchSyncLogs();
    }, pollIntervalMs);

    return () => clearInterval(interval);
  }, [pollIntervalMs]);

  const totalRegistered = syncStatuses.length;
  const successfulCount = syncStatuses.filter(s => s.last_attempt_status === 'SUCCESS').length;
  const failedCount = syncStatuses.filter(s => s.last_attempt_status === 'FAILURE').length;
  
  const healthyRate = totalRegistered > 0 
    ? ((successfulCount / totalRegistered) * 100).toFixed(1) 
    : '0.0';

  return (
    <div className="flex-1 flex flex-col gap-4 p-5 overflow-y-auto max-h-full">
      {/* Header Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Settings className="w-5 h-5 text-purple-500" />
            Synchronization & Engine Center
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Orchestrate background yFinance crawlers, absolute database transaction boundaries, and derived technical indicator engine recalculations.
          </p>
        </div>
        <button
          onClick={() => fetchSyncLogs()}
          disabled={isSyncing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-300 hover:text-white transition text-xs font-semibold cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
          Refresh Stats
        </button>
      </div>

      {/* Quick Metrics KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 shrink-0">
        {/* Sync Rate */}
        <div className="p-4 rounded-xl border border-slate-800 bg-[#121620]/30 flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Sync Health Rate</span>
            <span className="text-2xl font-bold text-purple-400 mt-1 block">{healthyRate}%</span>
          </div>
          <Heart className="w-8 h-8 text-purple-500/25" />
        </div>

        {/* Registered */}
        <div className="p-4 rounded-xl border border-slate-800 bg-[#121620]/30 flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Registered Stocks</span>
            <span className="text-2xl font-bold text-white mt-1 block">{totalRegistered}</span>
          </div>
          <CheckCircle className="w-8 h-8 text-emerald-500/20" />
        </div>

        {/* Success */}
        <div className="p-4 rounded-xl border border-slate-800 bg-[#121620]/30 flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Synchronized (EOD)</span>
            <span className="text-2xl font-bold text-emerald-400 mt-1 block">{successfulCount}</span>
          </div>
          <CheckCircle className="w-8 h-8 text-emerald-500/20" />
        </div>

        {/* Failures */}
        <div className="p-4 rounded-xl border border-slate-800 bg-[#121620]/30 flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Triage Failures</span>
            <span className="text-2xl font-bold text-rose-400 mt-1 block">{failedCount}</span>
          </div>
          <AlertOctagon className="w-8 h-8 text-rose-500/20 animate-pulse" />
        </div>
      </div>

      {/* Control Actions Card */}
      <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/10 flex flex-col md:flex-row gap-4 justify-between items-center shrink-0">
        <div>
          <h3 className="text-sm font-bold text-white tracking-wide">Manual Job Dispatcher</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Manually trigger parallel background EOD downloads or force technical engine recalibrations.
          </p>
        </div>

        <div className="flex gap-3">
          {/* Crawl Job */}
          <button
            onClick={triggerFullSync}
            className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-purple-500/30 hover:border-purple-500 text-purple-400 hover:text-white rounded-lg text-xs font-bold transition duration-150 cursor-pointer shadow-lg shadow-purple-900/5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Trigger Crawl Sync
          </button>

          {/* Engine Recalculate */}
          <button
            onClick={() => triggerRecalculate()}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-bold transition duration-150 cursor-pointer shadow-lg shadow-purple-900/20"
          >
            <Cpu className="w-3.5 h-3.5" />
            Recalculate All Indicators
          </button>
        </div>
      </div>

      {/* Detail logs sub-tabs */}
      <div className="flex-1 bg-[#121620]/60 rounded-xl border border-slate-800/80 p-4 overflow-hidden flex flex-col min-h-[350px]">
        {/* Tabs Bar */}
        <div className="flex items-center gap-4 border-b border-slate-800 pb-3 mb-3 shrink-0">
          <button
            onClick={() => setActiveSubTab('history')}
            className={`flex items-center gap-1.5 pb-1 px-1 border-b-2 text-sm font-bold transition cursor-pointer ${
              activeSubTab === 'history'
                ? 'border-purple-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <History className="w-4 h-4" />
            Job Execution History
          </button>
          
          <button
            onClick={() => setActiveSubTab('status')}
            className={`flex items-center gap-1.5 pb-1 px-1 border-b-2 text-sm font-bold transition cursor-pointer ${
              activeSubTab === 'status'
                ? 'border-purple-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            Ticker Health Center
          </button>
        </div>

        {/* Dynamic Sub-Tab Content */}
        <div className="flex-1 overflow-y-auto">
          {activeSubTab === 'history' ? (
            <table className="w-full border-collapse text-left text-sm text-slate-300">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono">
                  <th className="py-2 px-3">Run ID</th>
                  <th className="py-2 px-3">Start Time</th>
                  <th className="py-2 px-3">End Time</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-center">Total Tickers</th>
                  <th className="py-2 px-3 text-center">Processed</th>
                  <th className="py-2 px-3 text-center">Failed</th>
                  <th className="py-2 px-3 text-center">Inserted Rows</th>
                  <th className="py-2 px-3 max-w-[200px]">Error Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {syncJobs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-slate-500 text-sm">
                      No crawler sync jobs recorded. Click 'Trigger Crawl Sync' to start EOD downloader threads.
                    </td>
                  </tr>
                ) : (
                  syncJobs.map((job) => {
                    const isRunning = job.status === 'RUNNING';
                    const isSuccess = job.status === 'SUCCESS';
                    
                    return (
                      <tr key={job.id} className="hover:bg-slate-900/40 transition">
                        <td className="py-3 px-3 font-mono font-semibold text-slate-300 truncate max-w-[120px]" title={job.run_id}>
                          {job.run_id}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-400 text-xs">{job.start_time}</td>
                        <td className="py-3 px-3 font-mono text-slate-400 text-xs">{job.end_time || '-'}</td>
                        <td className="py-3 px-3">
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                            isSuccess 
                              ? 'text-emerald-400 bg-emerald-950/20 border border-emerald-900/30' 
                              : isRunning
                              ? 'text-amber-400 bg-amber-950/20 border border-amber-900/30 animate-pulse'
                              : 'text-rose-400 bg-rose-950/20 border border-rose-900/30'
                          }`}>
                            {job.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center font-mono">{job.total_symbols}</td>
                        <td className="py-3 px-3 text-center font-mono text-emerald-400">{job.processed_symbols}</td>
                        <td className="py-3 px-3 text-center font-mono text-rose-400">{job.failed_symbols}</td>
                        <td className="py-3 px-3 text-center font-mono text-indigo-400">{job.records_inserted}</td>
                        <td className="py-3 px-3 text-xs text-rose-400 font-sans truncate max-w-[200px]" title={job.error_summary || ''}>
                          {job.error_summary || '-'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          ) : (
            // Ticker Health Center
            <table className="w-full border-collapse text-left text-sm text-slate-300">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono">
                  <th className="py-2.5 px-3">Ticker</th>
                  <th className="py-2.5 px-3">Last Sync Date</th>
                  <th className="py-2.5 px-3">Last Status</th>
                  <th className="py-2.5 px-3">Triage Error Log</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {syncStatuses.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-slate-500 text-sm">
                      No status states loaded.
                    </td>
                  </tr>
                ) : (
                  syncStatuses.map((state, idx) => {
                    const isSuccess = state.last_attempt_status === 'SUCCESS';
                    return (
                      <tr key={idx} className="hover:bg-slate-900/40 transition">
                        <td className="py-2.5 px-3 font-bold text-white font-mono">{state.symbol.replace('.NS', '')}</td>
                        <td className="py-2.5 px-3 font-mono text-slate-400 text-xs">{state.last_successful_sync_date}</td>
                        <td className="py-2.5 px-3">
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                            isSuccess 
                              ? 'text-emerald-400 bg-emerald-950/20' 
                              : 'text-rose-400 bg-rose-950/20'
                          }`}>
                            {state.last_attempt_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-xs text-rose-400 truncate max-w-[400px]" title={state.last_error_message || ''}>
                          {state.last_error_message || '-'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
