/**
 * Cyrus — Full Student Results Page (Sprint 4)
 * No login required — accessed via /results/{token}
 */

"use client";

import { useEffect, useState } from "react";
import {
  BookOpen, CheckCircle, AlertTriangle, Loader2,
  Download, TrendingUp, Target, Star
} from "lucide-react";

export default function ResultsPage({ params }: { params: { token: string } }) {
  const [report, setReport] = useState<any>(null);
  const [feedback, setFeedback] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // Resolve share token → get item_id (feedback_report_id or submission_id)
    fetch(`/api/v1/share/${params.token}`)
      .then(r => { if (!r.ok) throw new Error("Not found"); return r.json(); })
      .then(async item => {
        // Load feedback report
        const fbRes = await fetch(`/api/v1/feedback/${item.item_id}`);
        if (!fbRes.ok) throw new Error("Report not ready");
        return fbRes.json();
      })
      .then(data => {
        setReport(data);
        setFeedback(data.feedback);
      })
      .catch(() => setError("This link is invalid or expired. Ask your teacher for a new one."));
  }, [params.token]);

  if (error) return (
    <div className="min-h-screen bg-[var(--cyrus-bg)] flex items-center justify-center p-6">
      <div className="glass p-8 max-w-sm text-center border-red-500/20">
        <AlertTriangle size={36} className="text-amber-400 mx-auto mb-3" />
        <p className="text-white font-semibold">{error}</p>
      </div>
    </div>
  );

  if (!report) return (
    <div className="min-h-screen bg-[var(--cyrus-bg)] flex items-center justify-center">
      <Loader2 size={32} className="animate-spin text-violet-400" />
    </div>
  );

  const percentage = report.max_marks ? (report.total_marks / report.max_marks * 100) : 0;
  const grade = percentage >= 85 ? "A" : percentage >= 70 ? "B" : percentage >= 55 ? "C" : percentage >= 40 ? "D" : "F";
  const gradeColor = { A: "#10b981", B: "#60a5fa", C: "#f59e0b", D: "#f97316", F: "#ef4444" }[grade] ?? "#64748b";

  return (
    <div className="min-h-screen bg-[var(--cyrus-bg)] py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-5">

        {/* Hero */}
        <div className="glass p-7 text-center border-violet-600/30 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-600/10 to-transparent pointer-events-none" />
          <div className="relative z-10">
            <div style={{ color: gradeColor }}
              className="text-6xl font-black mb-2">{grade}</div>
            <h1 className="text-2xl font-bold text-white">{report.student_name}</h1>
            <p className="text-[var(--cyrus-muted)] text-sm mt-1 mb-3">{report.exam_name}</p>
            <div className="flex justify-center gap-6">
              <div className="text-center">
                <p className="text-3xl font-bold text-white">{report.total_marks}</p>
                <p className="text-xs text-[var(--cyrus-muted)]">/ {report.max_marks} marks</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-white">{percentage.toFixed(0)}%</p>
                <p className="text-xs text-[var(--cyrus-muted)]">score</p>
              </div>
            </div>
          </div>
        </div>

        {/* Summary */}
        {feedback?.summary && (
          <div className="glass p-5 border-violet-600/20">
            <div className="flex items-center gap-2 mb-2">
              <Star size={16} className="text-violet-400" />
              <p className="text-sm font-semibold text-white">From your teacher</p>
            </div>
            <p className="text-sm text-[var(--cyrus-muted)] leading-relaxed">{feedback.summary}</p>
            {feedback.positive_notes && (
              <p className="mt-2 text-sm text-emerald-400">{feedback.positive_notes}</p>
            )}
          </div>
        )}

        {/* Question breakdown */}
        {report.grades?.length > 0 && (
          <div className="glass">
            <div className="px-5 py-3 border-b border-[var(--cyrus-border)] flex items-center gap-2">
              <Target size={15} className="text-violet-400" />
              <p className="font-semibold text-white text-sm">Question Breakdown</p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--cyrus-border)]">
                  <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Question</th>
                  <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)]">Marks</th>
                  <th className="px-4 py-2 text-left text-xs text-[var(--cyrus-muted)] hidden sm:table-cell">Feedback</th>
                </tr>
              </thead>
              <tbody>
                {report.grades.map((g: any, i: number) => (
                  <tr key={i} className="border-b border-[var(--cyrus-border)]/50">
                    <td className="px-4 py-2.5 text-violet-300 text-xs font-mono">{g.question}</td>
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-white">{g.marks}</span>
                      <span className="text-[var(--cyrus-muted)] text-xs">/{g.max}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-[var(--cyrus-muted)] hidden sm:table-cell">{g.feedback}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Concept Gaps */}
        {feedback?.concept_gaps?.length > 0 && (
          <div className="glass p-5">
            <p className="font-semibold text-white text-sm mb-3 flex items-center gap-2">
              <TrendingUp size={15} className="text-amber-400" />
              Areas to Strengthen
            </p>
            <div className="space-y-2">
              {feedback.concept_gaps.map((g: any, i: number) => (
                <div key={i} className={`flex items-center gap-3 p-2.5 rounded-lg ${g.severity === "major" ? "bg-red-500/10 border border-red-500/20" : "bg-amber-500/10 border border-amber-500/20"}`}>
                  <div className={`w-2 h-2 rounded-full ${g.severity === "major" ? "bg-red-400" : "bg-amber-400"}`} />
                  <p className="text-sm text-white">{g.concept}</p>
                  <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${g.severity === "major" ? "badge-review" : "badge-processing"}`}>{g.severity}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Study Tips */}
        {feedback?.study_tips?.length > 0 && (
          <div className="glass p-5">
            <p className="font-semibold text-white text-sm mb-3 flex items-center gap-2">
              <BookOpen size={15} className="text-blue-400" />
              Study Plan
            </p>
            <div className="space-y-3">
              {feedback.study_tips.map((t: any, i: number) => (
                <div key={i} className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-violet-600/20 text-violet-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">{i + 1}</div>
                  <div>
                    <p className="text-sm font-medium text-white">{t.topic}</p>
                    <p className="text-xs text-[var(--cyrus-muted)] mt-0.5">{t.tip}</p>
                    {t.chapter_ref && <p className="text-xs text-violet-400 mt-0.5">{t.chapter_ref}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Download PDF */}
        {report.pdf_url && (
          <a href={`/api/v1/export/submission/${report.submission_id}/pdf`}
            className="glass p-4 flex items-center justify-center gap-2 text-sm font-medium text-violet-400 hover:text-violet-300 hover:border-violet-600/40 transition-all border border-[var(--cyrus-border)] rounded-xl">
            <Download size={16} />
            Download PDF Report
          </a>
        )}

        <p className="text-center text-xs text-[var(--cyrus-muted)]">Graded by Cyrus AI · Reviewed by your teacher</p>
      </div>
    </div>
  );
}
