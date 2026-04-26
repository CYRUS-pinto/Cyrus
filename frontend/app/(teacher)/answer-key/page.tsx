/**
 * Cyrus — Answer Key Upload Page
 * Upload the model answer key for an exam — either as:
 * 1. Scanned image (processed through OCR pipeline)
 * 2. Manually typed text per question
 */
"use client";

import { useState, useEffect } from "react";
import { BookMarked, Upload, Plus, Trash2, CheckCircle } from "lucide-react";
import { useDropzone } from "react-dropzone";

export default function AnswerKeyPage() {
  const [exams, setExams] = useState<any[]>([]);
  const [examId, setExamId] = useState("");
  const [questions, setQuestions] = useState<{ num: string; text: string; marks: number }[]>([]);
  const [mode, setMode] = useState<"text" | "image">("text");
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetch("/api/v1/exams/").then(r => r.ok ? r.json() : []).then(es => {
      setExams(es);
      if (es.length) setExamId(es[0].id);
    });
  }, []);

  // Load existing answer key when exam changes
  useEffect(() => {
    if (!examId) return;
    fetch(`/api/v1/answer-keys/${examId}`).then(r => {
      if (!r.ok) return null;
      return r.json();
    }).then(data => {
      if (data?.structured_json?.questions) {
        setQuestions(data.structured_json.questions.map((q: any) => ({
          num: q.num, text: q.answer_text, marks: q.marks ?? 0
        })));
      }
    }).catch(() => {});
  }, [examId]);

  // Dropzone for image upload
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "image/*": [], "application/pdf": [] },
    onDrop: async ([file]) => {
      if (!examId || !file) return;
      setUploading(true);
      const form = new FormData();
      form.append("file", file);
      await fetch(`/api/v1/answer-keys/${examId}/upload`, { method: "POST", body: form });
      setUploading(false);
      setSaved(true);
    },
  });

  async function saveTextKey() {
    if (!examId) return;
    const body = { questions: questions.map(q => ({ num: q.num, answer_text: q.text, marks: Number(q.marks) })) };
    const r = await fetch(`/api/v1/answer-keys/${examId}/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.ok) setSaved(true);
  }

  function addQuestion() {
    setQuestions(qs => [...qs, { num: String(qs.length + 1), text: "", marks: 2 }]);
    setSaved(false);
  }

  function removeQuestion(i: number) {
    setQuestions(qs => qs.filter((_, idx) => idx !== i));
    setSaved(false);
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center gap-3">
        <BookMarked size={22} className="text-violet-400" />
        <h2 className="text-xl font-bold text-white">Answer Key</h2>
      </div>

      {/* Exam selector */}
      <div className="glass p-4 space-y-3">
        <label className="text-xs text-[var(--cyrus-muted)] block">Select Exam</label>
        <select value={examId} onChange={e => { setExamId(e.target.value); setSaved(false); }}
          className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none">
          {exams.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>

        {/* Mode tabs */}
        <div className="flex gap-2">
          {(["text", "image"] as const).map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === m ? "bg-violet-600 text-white" : "border border-[var(--cyrus-border)] text-[var(--cyrus-muted)] hover:border-violet-600/50"}`}>
              {m === "text" ? "Type Key" : "Upload Scan"}
            </button>
          ))}
        </div>
      </div>

      {mode === "image" ? (
        <div className="glass p-6">
          <div {...getRootProps()} className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${isDragActive ? "border-violet-600 bg-violet-600/10" : "border-[var(--cyrus-border)] hover:border-violet-600/50"}`}>
            <input {...getInputProps()} />
            <Upload size={28} className={`mx-auto mb-3 ${isDragActive ? "text-violet-400" : "text-[var(--cyrus-muted)]"}`} />
            <p className="text-sm font-medium text-white">{uploading ? "Uploading..." : isDragActive ? "Drop here" : "Drop answer key image or PDF"}</p>
            <p className="text-xs text-[var(--cyrus-muted)] mt-1">It will be run through the same OCR pipeline as student papers</p>
          </div>
          {saved && <div className="flex items-center gap-2 mt-4 text-emerald-400 text-sm"><CheckCircle size={16} /> Queued for OCR processing</div>}
        </div>
      ) : (
        <div className="glass">
          <div className="border-b border-[var(--cyrus-border)] px-5 py-3 flex items-center justify-between">
            <p className="text-sm font-medium text-white">Questions</p>
            <button onClick={addQuestion} className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300">
              <Plus size={14} /> Add Question
            </button>
          </div>
          <div className="divide-y divide-[var(--cyrus-border)]">
            {questions.map((q, i) => (
              <div key={i} className="p-4 space-y-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-violet-400 w-8">Q{q.num}</span>
                  <input type="number" min="0.5" step="0.5"
                    className="w-20 px-2 py-1.5 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-xs focus:border-violet-600 focus:outline-none"
                    placeholder="marks" value={q.marks}
                    onChange={e => setQuestions(qs => qs.map((item, idx) => idx === i ? { ...item, marks: Number(e.target.value) } : item))} />
                  <span className="text-xs text-[var(--cyrus-muted)]">marks</span>
                  <button onClick={() => removeQuestion(i)} className="ml-auto text-[var(--cyrus-muted)] hover:text-red-400 transition-colors">
                    <Trash2 size={13} />
                  </button>
                </div>
                <textarea
                  className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-sm text-white rounded-lg focus:border-violet-600 focus:outline-none resize-none"
                  placeholder="Model answer for this question..."
                  rows={2} value={q.text}
                  onChange={e => {
                    setSaved(false);
                    setQuestions(qs => qs.map((item, idx) => idx === i ? { ...item, text: e.target.value } : item));
                  }}
                />
              </div>
            ))}
            {questions.length === 0 && (
              <p className="p-6 text-center text-sm text-[var(--cyrus-muted)]">Add questions above, or switch to Upload Scan mode.</p>
            )}
          </div>
          <div className="p-4 border-t border-[var(--cyrus-border)] flex items-center justify-between">
            {saved && <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle size={13} /> Saved</span>}
            <button onClick={saveTextKey}
              className="ml-auto px-5 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
              Save Answer Key
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
