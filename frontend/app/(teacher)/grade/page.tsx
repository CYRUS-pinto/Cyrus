/**
 * Cyrus — Full Grade Review Page (Sprint 3)
 * 
 * Shows each student submission alongside AI grades.
 * Teacher can:
 * - View scanned page images and OCR text side-by-side
 * - See AI marks + confidence per question  
 * - Override any mark with one click
 * - Batch approve high-confidence grades
 * - Flag low-confidence grades for manual review
 */

"use client";

import { useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";
import {
  CheckCircle, AlertTriangle, Edit3, ChevronDown, ChevronRight,
  Users, Loader2, TrendingUp, Download, Zap
} from "lucide-react";

const ConfidenceBadge = ({ conf }: { conf: number }) => {
  if (conf >= 0.85) return <span className="px-2 py-0.5 rounded-full text-xs badge-completed">High {(conf * 100).toFixed(0)}%</span>;
  if (conf >= 0.65) return <span className="px-2 py-0.5 rounded-full text-xs badge-processing">Med {(conf * 100).toFixed(0)}%</span>;
  return <span className="px-2 py-0.5 rounded-full text-xs badge-review">Low {(conf * 100).toFixed(0)}%</span>;
};

const OverrideModal = ({ grade, onSave, onClose }: any) => {
  const [marks, setMarks] = useState(grade.awarded_marks ?? grade.override_marks ?? 0);
  const [note, setNote] = useState("");

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="glass p-6 w-full max-w-sm space-y-4 border-violet-600/30">
        <h3 className="font-bold text-white">Override AI Grade</h3>
        <p className="text-xs text-[var(--cyrus-muted)]">AI suggested: {grade.awarded_marks}/{grade.max_marks}</p>
        <div>
          <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Your mark</label>
          <input type="number" min="0" max={grade.max_marks} step="0.5"
            className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none"
            value={marks} onChange={e => setMarks(Number(e.target.value))} />
        </div>
        <div>
          <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Note (optional)</label>
          <input className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none"
            placeholder="Reason for override"
            value={note} onChange={e => setNote(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <button onClick={() => onSave({ marks, note })} className="flex-1 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">Save Override</button>
          <button onClick={onClose} className="px-4 py-2 border border-[var(--cyrus-border)] rounded-lg text-sm transition-colors hover:border-violet-600/50">Cancel</button>
        </div>
      </div>
    </div>
  );
};

const SubmissionCard = ({ submission, onRefresh }: any) => {
  const [expanded, setExpanded] = useState(false);
  const [grades, setGrades] = useState<any[]>([]);
  const [loadingGrades, setLoadingGrades] = useState(false);
  const [overrideTarget, setOverrideTarget] = useState<any>(null);

  async function loadGrades() {
    if (grades.length) { setExpanded(!expanded); return; }
    setExpanded(true);
    setLoadingGrades(true);
    const r = await fetch(`/api/v1/grade/submission/${submission.id}`);
    if (r.ok) setGrades(await r.json());
    setLoadingGrades(false);
  }

  async function saveOverride(gradeId: string, data: { marks: number; note: string }) {
    await fetch(`/api/v1/grade/grade/${gradeId}/override`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ marks: data.marks, note: data.note }),
    });
    setOverrideTarget(null);
    // Re-load grades
    const r = await fetch(`/api/v1/grade/submission/${submission.id}`);
    if (r.ok) setGrades(await r.json());
    onRefresh?.();
  }

  async function triggerGrading() {
    await fetch(`/api/v1/grade/submission/${submission.id}/trigger`, { method: "POST" });
    onRefresh?.();
  }

  const total = grades.reduce((s, g) => s + (g.teacher_override ? g.override_marks : g.awarded_marks), 0);
  const maxTotal = grades.reduce((s, g) => s + g.max_marks, 0);

  return (
    <>
      {overrideTarget && (
        <OverrideModal
          grade={overrideTarget}
          onSave={(d: any) => saveOverride(overrideTarget.id, d)}
          onClose={() => setOverrideTarget(null)}
        />
      )}
      <div className="glass overflow-hidden">
        <div
          className="flex items-center gap-4 p-4 cursor-pointer hover:bg-white/2 transition-colors"
          onClick={loadGrades}
        >
          {expanded ? <ChevronDown size={16} className="text-[var(--cyrus-muted)]" /> : <ChevronRight size={16} className="text-[var(--cyrus-muted)]" />}
          <div className="flex-1">
            <p className="font-medium text-white">{submission.student_name ?? "Unknown Student"}</p>
            <p className="text-xs text-[var(--cyrus-muted)]">
              {submission.reg_no && `${submission.reg_no} · `}
              Status: <span className={`font-medium ${submission.status === "completed" ? "text-emerald-400" : "text-amber-400"}`}>{submission.status}</span>
            </p>
          </div>
          <div className="text-right">
            {submission.total_marks != null ? (
              <p className="font-bold text-white text-lg">{submission.total_marks}</p>
            ) : (
              <button onClick={e => { e.stopPropagation(); triggerGrading(); }}
                className="px-3 py-1 bg-violet-600/20 hover:bg-violet-600/40 text-violet-400 rounded-lg text-xs font-medium transition-colors flex items-center gap-1">
                <Zap size={12} /> Grade
              </button>
            )}
          </div>
        </div>

        {expanded && (
          <div className="border-t border-[var(--cyrus-border)]">
            {loadingGrades ? (
              <div className="p-6 flex justify-center"><Loader2 size={20} className="animate-spin text-violet-400" /></div>
            ) : grades.length === 0 ? (
              <p className="p-4 text-sm text-[var(--cyrus-muted)]">No grades yet. Click Grade above.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--cyrus-border)]">
                    <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Question</th>
                    <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Marks</th>
                    <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Confidence</th>
                    <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Feedback</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {grades.map(grade => (
                    <tr key={grade.id} className={`border-b border-[var(--cyrus-border)]/50 hover:bg-white/2 ${grade.flagged ? "bg-red-500/5" : ""}`}>
                      <td className="px-4 py-2.5 font-mono text-xs text-violet-300">{grade.question_id?.slice(0, 6) ?? "Q?"}</td>
                      <td className="px-4 py-2.5">
                        <span className={grade.teacher_override ? "line-through text-[var(--cyrus-muted)] text-xs mr-2" : "text-white font-medium"}>
                          {grade.awarded_marks}/{grade.max_marks}
                        </span>
                        {grade.teacher_override && (
                          <span className="text-emerald-400 font-medium">{grade.override_marks}/{grade.max_marks} ✎</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <ConfidenceBadge conf={grade.ai_confidence ?? 0} />
                      </td>
                      <td className="px-4 py-2.5 text-xs text-[var(--cyrus-muted)] max-w-[200px] truncate">{grade.ai_feedback}</td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => setOverrideTarget(grade)}
                          className="p-1.5 rounded-lg hover:bg-violet-600/20 text-[var(--cyrus-muted)] hover:text-violet-400 transition-colors">
                          <Edit3 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                {grades.length > 0 && (
                  <tfoot>
                    <tr className="border-t border-[var(--cyrus-border)]">
                      <td className="px-4 py-2 text-xs font-medium text-white" colSpan={2}>Total: {total.toFixed(1)} / {maxTotal}</td>
                      <td colSpan={3} className="px-4 py-2 text-right">
                        <a href={`/api/v1/export/submission/${submission.id}/pdf`} target="_blank"
                          className="text-xs text-violet-400 hover:underline flex items-center gap-1 justify-end">
                          <Download size={12} /> Download PDF
                        </a>
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default function GradePage() {
  const params = useSearchParams();
  const examId = params.get("exam");
  const [exams, setExams] = useState<any[]>([]);
  const [selectedExam, setSelectedExam] = useState(examId ?? "");
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [key, setKey] = useState(0);

  useEffect(() => {
    fetch("/api/v1/exams/").then(r => r.ok ? r.json() : []).then(setExams).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedExam) return;
    setLoading(true);
    fetch(`/api/v1/upload/session/submissions?exam_id=${selectedExam}`)
      .then(r => r.ok ? r.json() : [])
      .then(setSubmissions)
      .catch(() => setSubmissions([]))
      .finally(() => setLoading(false));
  }, [selectedExam, key]);

  async function gradeAll() {
    await Promise.all(submissions.filter(s => !s.total_marks).map(s =>
      fetch(`/api/v1/grade/submission/${s.id}/trigger`, { method: "POST" })
    ));
    setKey(k => k + 1);
  }

  const graded = submissions.filter(s => s.status === "completed").length;

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Grade Review</h2>
          <p className="text-sm text-[var(--cyrus-muted)] mt-0.5">{graded}/{submissions.length} submissions graded</p>
        </div>
        <div className="flex gap-2">
          <select
            value={selectedExam}
            onChange={e => setSelectedExam(e.target.value)}
            className="px-3 py-2 bg-[var(--cyrus-surface)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none"
          >
            <option value="">Select exam...</option>
            {exams.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          {submissions.length > 0 && (
            <button onClick={gradeAll}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
              <Zap size={15} /> Grade All
            </button>
          )}
          {selectedExam && (
            <a href={`/api/v1/export/exam/${selectedExam}/csv`}
              className="flex items-center gap-2 px-3 py-2 border border-[var(--cyrus-border)] hover:border-violet-600/50 rounded-lg text-sm transition-colors">
              <Download size={15} /> CSV
            </a>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 size={28} className="animate-spin text-violet-400" /></div>
      ) : submissions.length === 0 ? (
        <div className="glass p-10 text-center">
          <Users size={36} className="mx-auto mb-3 text-[var(--cyrus-muted)] opacity-40" />
          <p className="text-[var(--cyrus-muted)]">{selectedExam ? "No submissions yet for this exam." : "Select an exam to begin."}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {submissions.map(sub => (
            <SubmissionCard key={`${sub.id}-${key}`} submission={sub} onRefresh={() => setKey(k => k + 1)} />
          ))}
        </div>
      )}
    </div>
  );
}
