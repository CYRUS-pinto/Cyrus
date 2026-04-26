/**
 * Cyrus — Mobile Upload Page
 * 
 * This page opens on the TEACHER'S PHONE after scanning the QR code.
 * It provides a phone-optimised interface for:
 * 1. [+ New Student] to start a new student's papers
 * 2. Camera button to photograph one page
 * 3. Live page counter per student
 * 4. Session summary visible at all times
 * 
 * URL: /session/{token}
 * This token matches the UploadSession.qr_token in the database.
 */

"use client";

import { useState, useEffect } from "react";
import { Camera, UserPlus, CheckCircle2, Loader2 } from "lucide-react";

export default function MobileSessionPage({ params }: { params: { token: string } }) {
  const { token } = params;

  const [session, setSession] = useState<any>(null);
  const [currentSubmission, setCurrentSubmission] = useState<any>(null);
  const [pageCount, setPageCount] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [totalStudents, setTotalStudents] = useState(0);
  const [error, setError] = useState("");
  const [studentName, setStudentName] = useState("");

  // Load session on mount
  useEffect(() => {
    fetch(`/api/v1/upload/session/${token}`)
      .then(r => r.json())
      .then(data => setSession(data))
      .catch(() => setError("Session not found. Please re-scan the QR code."));
  }, [token]);

  // Start a new student group
  async function newStudent() {
    const res = await fetch(`/api/v1/upload/session/${token}/new-student`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_name: studentName }),
    });
    if (!res.ok) { setError("Could not create student group"); return; }
    const data = await res.json();
    setCurrentSubmission(data);
    setPageCount(0);
    setTotalStudents(t => t + 1);
    setStudentName("");
  }

  // Capture + upload one photo
  async function capturePhoto(file: File) {
    if (!currentSubmission) return;
    setUploading(true);

    const form = new FormData();
    form.append("submission_id", currentSubmission.submission_id);
    form.append("page_number", String(pageCount + 1));
    form.append("file", file);

    const res = await fetch(`/api/v1/upload/session/${token}/upload-page`, {
      method: "POST",
      body: form,
    });

    setUploading(false);
    if (res.ok) {
      setPageCount(c => c + 1);
    } else {
      setError("Upload failed. Please try again.");
    }
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[var(--cyrus-bg)] flex items-center justify-center p-6">
        <div className="glass p-6 text-center max-w-sm">
          <p className="text-red-400 font-medium">{error}</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen bg-[var(--cyrus-bg)] flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-violet-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--cyrus-bg)] p-4 space-y-4 max-w-md mx-auto">

      {/* Header */}
      <div className="glass p-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--cyrus-muted)]">Upload Session</p>
          <p className="font-bold text-white">{totalStudents} students · {pageCount} pages</p>
        </div>
        <div className="w-2 h-2 rounded-full bg-emerald-400 sync-pulse" />
      </div>

      {/* Current student */}
      {currentSubmission ? (
        <div className="glass p-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-violet-600/20 flex items-center justify-center text-violet-400 font-bold">
              {totalStudents}
            </div>
            <div>
              <p className="font-medium text-white">{currentSubmission.initial_name}</p>
              <p className="text-xs text-[var(--cyrus-muted)]">{pageCount} pages uploaded</p>
            </div>
          </div>

          {/* Camera button */}
          <label className="block">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={e => { if (e.target.files?.[0]) capturePhoto(e.target.files[0]); e.target.value = ""; }}
            />
            <div className={`
              w-full h-24 rounded-xl border-2 border-dashed flex items-center justify-center gap-3 cursor-pointer transition-all
              ${uploading
                ? "border-violet-600 bg-violet-600/10"
                : "border-[var(--cyrus-border)] hover:border-violet-600/50 hover:bg-violet-600/5"
              }
            `}>
              {uploading
                ? <><Loader2 size={24} className="animate-spin text-violet-400" /><span className="text-violet-400 font-medium">Uploading...</span></>
                : <><Camera size={24} className="text-violet-400" /><span className="text-white font-medium">Take Photo</span></>
              }
            </div>
          </label>

          <p className="text-xs text-center text-[var(--cyrus-muted)]">
            Photograph one page at a time. Pages auto-order by time.
          </p>
        </div>
      ) : (
        <div className="glass p-5 text-center text-[var(--cyrus-muted)] text-sm">
          Press "New Student" to start photographing the first paper.
        </div>
      )}

      {/* New Student button */}
      <div className="glass p-4 space-y-3">
        <input
          className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] rounded-lg text-sm focus:outline-none focus:border-violet-600 text-white placeholder-[var(--cyrus-muted)]"
          placeholder="Student name (optional — auto-detected)"
          value={studentName}
          onChange={e => setStudentName(e.target.value)}
        />
        <button
          onClick={newStudent}
          className="w-full py-3 bg-violet-600 hover:bg-violet-500 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-colors"
        >
          <UserPlus size={18} />
          + New Student
        </button>
      </div>

    </div>
  );
}
