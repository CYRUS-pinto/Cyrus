"""Share page for Cyrus — teacher creates links, revokes them."""
"use client";

import { useState, useEffect } from "react";
import { Share2, Plus, Copy, Trash2, CheckCircle, Clock } from "lucide-react";

const MODE_LABELS: Record<string, string> = {
  submission: "Student Paper",
  exam: "Exam Results",
  feedback: "Feedback Report",
};

export default function SharePage() {
  const [items, setItems] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ item_type: "exam", item_id: "", email: "", expiry_days: 7 });
  const [copied, setCopied] = useState<string | null>(null);

  function copyLink(token: string) {
    navigator.clipboard.writeText(`${location.origin}/results/${token}`);
    setCopied(token);
    setTimeout(() => setCopied(null), 2000);
  }

  async function createShare() {
    const r = await fetch("/api/v1/share/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (r.ok) {
      const data = await r.json();
      setItems(prev => [{ ...data, item_type: form.item_type }, ...prev]);
      setCreating(false);
    }
  }

  async function revokeShare(token: string) {
    await fetch(`/api/v1/share/${token}`, { method: "DELETE" });
    setItems(prev => prev.filter(i => i.token !== token));
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Share Links</h2>
        <button onClick={() => setCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
          <Plus size={15} /> Create Link
        </button>
      </div>

      {creating && (
        <div className="glass p-5 space-y-3 border-violet-600/30">
          <h3 className="font-semibold text-white">New Share Link</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Share Type</label>
              <select value={form.item_type} onChange={e => setForm(f => ({ ...f, item_type: e.target.value }))}
                className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none">
                <option value="exam">Exam Results</option>
                <option value="submission">Student Paper</option>
                <option value="feedback">Feedback Report</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Expires (days)</label>
              <input type="number" min="1" max="365" value={form.expiry_days}
                onChange={e => setForm(f => ({ ...f, expiry_days: Number(e.target.value) }))}
                className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none" />
            </div>
          </div>
          <div>
            <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Item ID</label>
            <input value={form.item_id} onChange={e => setForm(f => ({ ...f, item_id: e.target.value }))}
              placeholder="Exam ID or Submission ID"
              className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--cyrus-muted)] block mb-1">Recipient email (optional)</label>
            <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              placeholder="student@example.com"
              className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] text-white rounded-lg text-sm focus:border-violet-600 focus:outline-none" />
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={createShare} className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">Create</button>
            <button onClick={() => setCreating(false)} className="px-4 py-2 border border-[var(--cyrus-border)] rounded-lg text-sm hover:border-violet-600/50 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {items.length === 0 && (
          <div className="glass p-8 text-center text-[var(--cyrus-muted)]">
            <Share2 size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No share links created yet.</p>
          </div>
        )}
        {items.map((item, i) => (
          <div key={i} className="glass p-4 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{MODE_LABELS[item.item_type] ?? item.item_type}</p>
              <p className="text-xs text-[var(--cyrus-muted)] truncate mt-0.5">
                {`${location.origin}/results/${item.token}`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-xs text-[var(--cyrus-muted)] flex items-center gap-1">
                <Clock size={11} /> {item.expires_days}d
              </span>
              <button onClick={() => copyLink(item.token)}
                className={`p-1.5 rounded-lg transition-colors ${copied === item.token ? "text-emerald-400 bg-emerald-400/10" : "text-[var(--cyrus-muted)] hover:text-violet-400 hover:bg-violet-600/10"}`}>
                {copied === item.token ? <CheckCircle size={15} /> : <Copy size={15} />}
              </button>
              <button onClick={() => revokeShare(item.token)}
                className="p-1.5 rounded-lg text-[var(--cyrus-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors">
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
