/**
 * Cyrus — Teacher Dashboard
 * 
 * The first page a teacher sees. Shows an overview of:
 * - Total classes, exams, students graded
 * - Recent exams with status
 * - Quick action buttons
 * - Grading queue (papers waiting to be processed)
 */

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  GraduationCap, BookOpen, CheckCircle,
  Clock, Upload, Plus, ArrowRight, Zap, TrendingUp
} from "lucide-react";

const StatCard = ({ label, value, icon: Icon, color }: any) => (
  <div className="glass p-5 flex items-center gap-4">
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
      <Icon size={22} />
    </div>
    <div>
      <p className="text-3xl font-bold text-white">{value}</p>
      <p className="text-sm text-[var(--cyrus-muted)] mt-0.5">{label}</p>
    </div>
  </div>
);

const StatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, string> = {
    draft: "badge-draft",
    uploading: "badge-uploading",
    grading: "badge-processing",
    completed: "badge-completed",
    needs_review: "badge-review",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "badge-draft"}`}>
      {status.replace("_", " ")}
    </span>
  );
};

export default function DashboardPage() {
  const [stats, setStats] = useState({ classes: 0, exams: 0, graded: 0, pending: 0 });
  const [recentExams, setRecentExams] = useState<any[]>([]);

  useEffect(() => {
    // Load dashboard data from API
    fetch("/api/v1/classes/").then(r => r.ok ? r.json() : []).then(classes => {
      setStats(s => ({ ...s, classes: classes.length }));
    }).catch(() => {});

    fetch("/api/v1/exams/").then(r => r.ok ? r.json() : []).then(exams => {
      setRecentExams(exams.slice(0, 5));
      setStats(s => ({
        ...s,
        exams: exams.length,
        graded: exams.filter((e: any) => e.status === "completed").length,
        pending: exams.filter((e: any) => e.status === "grading").length,
      }));
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-8">

      {/* Welcome Banner */}
      <div className="glass p-6 border-violet-600/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-violet-600/10 to-transparent pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={18} className="text-violet-400" />
            <span className="text-sm font-medium text-violet-400">Cyrus AI Grading Platform</span>
          </div>
          <h2 className="text-2xl font-bold text-white mb-1">Welcome back</h2>
          <p className="text-[var(--cyrus-muted)] text-sm">
            Grade exam papers 10× faster with AI-powered OCR and semantic scoring.
          </p>
          <div className="flex gap-3 mt-4">
            <Link href="/upload">
              <button className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
                <Upload size={15} />
                Upload Papers
              </button>
            </Link>
            <Link href="/classes">
              <button className="flex items-center gap-2 px-4 py-2 border border-[var(--cyrus-border)] hover:border-violet-600/50 rounded-lg text-sm font-medium transition-colors">
                <Plus size={15} />
                New Class
              </button>
            </Link>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Classes"    value={stats.classes} icon={GraduationCap} color="bg-violet-600/20 text-violet-400" />
        <StatCard label="Exams"      value={stats.exams}   icon={BookOpen}      color="bg-blue-600/20 text-blue-400" />
        <StatCard label="Graded"     value={stats.graded}  icon={CheckCircle}   color="bg-emerald-600/20 text-emerald-400" />
        <StatCard label="In Queue"   value={stats.pending} icon={Clock}         color="bg-amber-600/20 text-amber-400" />
      </div>

      {/* Recent Exams */}
      <div className="glass">
        <div className="flex items-center justify-between p-5 border-b border-[var(--cyrus-border)]">
          <h3 className="font-semibold text-white">Recent Exams</h3>
          <Link href="/exams" className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
            View all <ArrowRight size={12} />
          </Link>
        </div>
        <div className="divide-y divide-[var(--cyrus-border)]">
          {recentExams.length > 0 ? recentExams.map((exam: any) => (
            <div key={exam.id} className="flex items-center justify-between p-4 hover:bg-white/2 transition-colors">
              <div>
                <p className="text-sm font-medium text-white">{exam.name}</p>
                <p className="text-xs text-[var(--cyrus-muted)] mt-0.5">
                  {exam.total_marks} marks
                  {exam.exam_date && ` · ${new Date(exam.exam_date).toLocaleDateString()}`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={exam.status} />
                <Link href={`/grade?exam=${exam.id}`}>
                  <button className="text-xs px-3 py-1.5 border border-[var(--cyrus-border)] hover:border-violet-600/50 rounded-lg transition-colors">
                    Open
                  </button>
                </Link>
              </div>
            </div>
          )) : (
            <div className="p-8 text-center text-[var(--cyrus-muted)] text-sm">
              <TrendingUp size={32} className="mx-auto mb-3 opacity-30" />
              <p>No exams yet.</p>
              <Link href="/exams" className="text-violet-400 hover:underline text-xs mt-1 inline-block">
                Create your first exam →
              </Link>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
