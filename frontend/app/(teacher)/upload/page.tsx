/**
 * Cyrus — Upload Page
 * 
 * The teacher's main workflow:
 * 1. Select an exam
 * 2. Click "Generate QR Code"
 * 3. QR appears → scan with phone
 * 4. Phone opens mobile upload interface
 * 5. Teacher photographs each student's booklet, pressing [+ New Student] between each
 * 6. Progress shown in real-time
 * 7. Click "Close Session" when done
 */

"use client";

import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Upload, QrCode, Users, X, CheckCircle } from "lucide-react";

export default function UploadPage() {
  const [examId, setExamId] = useState("");
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [closed, setClosed] = useState(false);

  async function generateQR() {
    if (!examId) return;
    setLoading(true);
    try {
      const res = await fetch("/api/v1/upload/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exam_id: examId }),
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data);
      }
    } finally {
      setLoading(false);
    }
  }

  async function closeSession() {
    if (!session) return;
    await fetch(`/api/v1/upload/session/${session.qr_token}/close`, { method: "POST" });
    setClosed(true);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">

      {/* Step 1 — Select Exam */}
      {!session && (
        <div className="glass p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <QrCode size={20} className="text-violet-400" />
            Generate Upload QR Code
          </h2>
          <p className="text-sm text-[var(--cyrus-muted)]">
            Enter your exam ID, generate the QR, scan it with your phone to begin photographing papers.
          </p>
          <div className="space-y-3">
            <label className="block text-sm font-medium text-white">Exam ID</label>
            <input
              className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] rounded-lg text-sm focus:outline-none focus:border-violet-600 transition-colors"
              placeholder="Paste exam ID here"
              value={examId}
              onChange={e => setExamId(e.target.value)}
            />
            <button
              onClick={generateQR}
              disabled={!examId || loading}
              className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <Upload size={16} />
              {loading ? "Generating..." : "Generate QR Code"}
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — QR Code Display */}
      {session && !closed && (
        <div className="glass p-6 space-y-5 text-center">
          <div className="inline-flex items-center gap-2 bg-emerald-400/10 text-emerald-400 px-3 py-1.5 rounded-full text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 sync-pulse" />
            Session Active
          </div>

          <div>
            <h2 className="text-xl font-bold text-white mb-1">Scan QR with your phone</h2>
            <p className="text-sm text-[var(--cyrus-muted)]">
              Point your camera at this code to open the upload interface
            </p>
          </div>

          {/* QR Code */}
          <div className="inline-block p-4 bg-white rounded-2xl">
            <QRCodeSVG
              value={session.mobile_url}
              size={200}
              level="M"
              includeMargin={false}
            />
          </div>

          <div className="text-xs text-[var(--cyrus-muted)] break-all">
            {session.mobile_url}
          </div>

          {/* Stats */}
          <div className="flex justify-center gap-8 py-3 border-y border-[var(--cyrus-border)]">
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{session.student_count ?? 0}</p>
              <p className="text-xs text-[var(--cyrus-muted)]">Students</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{session.page_count ?? 0}</p>
              <p className="text-xs text-[var(--cyrus-muted)]">Pages</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={closeSession}
              className="flex-1 py-2.5 border border-[var(--cyrus-border)] hover:border-red-500/50 hover:text-red-400 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <X size={15} />
              Close Session
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Closed confirmation */}
      {closed && (
        <div className="glass p-8 text-center space-y-3">
          <CheckCircle size={40} className="text-emerald-400 mx-auto" />
          <h2 className="text-xl font-bold text-white">Session closed</h2>
          <p className="text-sm text-[var(--cyrus-muted)]">
            All uploaded papers are now being processed by the OCR pipeline.
            Check the <a href="/grade" className="text-violet-400 hover:underline">Grade tab</a> for results.
          </p>
        </div>
      )}

    </div>
  );
}
