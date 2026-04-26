/**
 * Cyrus — Adaptive Learning / Fine-Tuning Page (Sprint 6)
 * 
 * Shows the OCR correction count and the fine-tuning trigger button.
 * Only available when enough corrections have been collected.
 */

"use client";

import { useState, useEffect } from "react";
import { Zap, CheckCircle, Loader2, AlertTriangle, TrendingUp, Clock } from "lucide-react";

export default function AdaptivePage() {
  const [stats, setStats] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetch("/api/v1/adaptive/corrections/stats").then(r => r.ok ? r.json() : null).then(setStats);
    fetch("/api/v1/adaptive/finetune/jobs").then(r => r.ok ? r.json() : []).then(setJobs);
  }, []);

  async function triggerFineTune() {
    setTriggering(true);
    try {
      const r = await fetch("/api/v1/adaptive/finetune/trigger", { method: "POST" });
      const data = await r.json();
      if (r.ok) {
        setMessage(data.message);
        setStats((s: any) => ({ ...s, fine_tuning_available: false }));
      } else {
        setMessage(data.detail ?? "Failed to trigger fine-tuning");
      }
    } finally {
      setTriggering(false);
    }
  }

  const progressPercent = stats ? Math.min(100, (stats.unused_corrections / stats.threshold) * 100) : 0;

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-bold text-white flex items-center gap-2">
        <Zap size={22} className="text-violet-400" />
        Adaptive Fine-Tuning
      </h2>

      {/* Correction progress */}
      <div className="glass p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold text-white">OCR Corrections Collected</p>
            <p className="text-xs text-[var(--cyrus-muted)] mt-0.5">
              Every time you correct a misread word, Cyrus learns from it.
              Once you reach {stats?.threshold ?? "..."} corrections, fine-tuning becomes available.
            </p>
          </div>
          <span className="text-2xl font-bold text-white">{stats?.unused_corrections ?? "—"}</span>
        </div>

        {/* Progress bar */}
        <div className="h-2 bg-[var(--cyrus-bg)] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-600 to-purple-400 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-xs text-[var(--cyrus-muted)]">
          <span>{stats?.unused_corrections ?? 0} / {stats?.threshold ?? "..."} corrections</span>
          {stats?.still_needed > 0 && <span>{stats.still_needed} more needed</span>}
        </div>

        {stats?.fine_tuning_available && (
          <div className="p-3 bg-violet-600/10 border border-violet-600/20 rounded-lg">
            <p className="text-violet-300 text-sm font-medium mb-2">✨ Fine-tuning is ready!</p>
            <p className="text-violet-300/70 text-xs">
              This will take 1–4 hours. Cyrus will retrain the OCR model on your school's specific handwriting style.
              Expected improvement: 30–50% lower error rate.
            </p>
          </div>
        )}

        <button
          onClick={triggerFineTune}
          disabled={!stats?.fine_tuning_available || triggering}
          className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
        >
          {triggering ? <><Loader2 size={15} className="animate-spin" /> Starting...</> : <><Zap size={15} /> Run Fine-Tuning</>}
        </button>

        {message && <p className="text-xs text-emerald-400">{message}</p>}
      </div>

      {/* Job history */}
      {jobs.length > 0 && (
        <div className="glass">
          <div className="px-5 py-3 border-b border-[var(--cyrus-border)]">
            <p className="font-semibold text-white text-sm">Fine-Tuning History</p>
          </div>
          <div className="divide-y divide-[var(--cyrus-border)]">
            {jobs.map(job => (
              <div key={job.id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white flex items-center gap-2">
                    {job.status === "completed" ? <CheckCircle size={14} className="text-emerald-400" /> :
                     job.status === "running" ? <Loader2 size={14} className="animate-spin text-violet-400" /> :
                     job.status === "failed" ? <AlertTriangle size={14} className="text-red-400" /> :
                     <Clock size={14} className="text-amber-400" />}
                    {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                  </p>
                  <p className="text-xs text-[var(--cyrus-muted)] mt-0.5">{job.corrections_used} corrections used</p>
                </div>
                {job.cer_before && job.cer_after && (
                  <div className="text-right">
                    <p className="text-xs text-emerald-400 font-medium">
                      {((job.cer_before - job.cer_after) / job.cer_before * 100).toFixed(1)}% fewer errors
                    </p>
                    <p className="text-xs text-[var(--cyrus-muted)]">{(job.cer_before * 100).toFixed(1)}% → {(job.cer_after * 100).toFixed(1)}% CER</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
