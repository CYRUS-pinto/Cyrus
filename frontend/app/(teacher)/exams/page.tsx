/**
 * Cyrus Exams Page — list all exams with status
 */
"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, BookOpen, ChevronRight, Calendar } from "lucide-react";

const STATUS_COLORS: Record<string,string> = { draft:"badge-draft", active:"badge-uploading", grading:"badge-processing", completed:"badge-completed" };

export default function ExamsPage() {
  const [exams, setExams] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", subject_id: "", total_marks: "30", exam_date: "" });

  useEffect(() => { fetch("/api/v1/exams/").then(r => r.json()).then(setExams).catch(() => {}); }, []);

  async function createExam() {
    const res = await fetch("/api/v1/exams/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({...form, total_marks: Number(form.total_marks)}) });
    if (res.ok) { const e = await res.json(); setExams(es => [e, ...es]); setCreating(false); }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Exams</h2>
        <button onClick={() => setCreating(true)} className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
          <Plus size={15} /> New Exam
        </button>
      </div>

      {creating && (
        <div className="glass p-5 space-y-3">
          <h3 className="font-semibold">Create Exam</h3>
          {[["name","Exam Name *"],["subject_id","Subject ID *"],["total_marks","Total Marks"],["exam_date","Exam Date (YYYY-MM-DD)"]].map(([k,l]) => (
            <div key={k}>
              <label className="text-xs text-[var(--cyrus-muted)] mb-1 block">{l}</label>
              <input className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] rounded-lg text-sm focus:outline-none focus:border-violet-600 text-white"
                value={(form as any)[k]} onChange={e => setForm(f => ({...f, [k]: e.target.value}))} />
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button onClick={createExam} className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">Create</button>
            <button onClick={() => setCreating(false)} className="px-4 py-2 border border-[var(--cyrus-border)] rounded-lg text-sm hover:border-violet-600/50 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {exams.length === 0 && <p className="text-[var(--cyrus-muted)] text-sm text-center py-12">No exams yet.</p>}
        {exams.map(exam => (
          <Link key={exam.id} href={`/grade?exam=${exam.id}`}>
            <div className="glass p-4 flex items-center gap-4 hover:border-violet-600/40 transition-all cursor-pointer">
              <div className="w-10 h-10 rounded-xl bg-blue-600/20 flex items-center justify-center">
                <BookOpen size={18} className="text-blue-400" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-white">{exam.name}</p>
                <div className="flex items-center gap-3 mt-0.5">
                  <p className="text-xs text-[var(--cyrus-muted)]">{exam.total_marks} marks</p>
                  {exam.exam_date && <p className="text-xs text-[var(--cyrus-muted)] flex items-center gap-1"><Calendar size={10} />{exam.exam_date}</p>}
                </div>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[exam.status] ?? "badge-draft"}`}>{exam.status}</span>
              <ChevronRight size={16} className="text-[var(--cyrus-muted)]" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
