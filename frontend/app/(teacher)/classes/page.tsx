/**
 * Cyrus Classes Page — list classes, create new, click to open
 */
"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, GraduationCap, Users, ChevronRight } from "lucide-react";

export default function ClassesPage() {
  const [classes, setClasses] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", year: "", section: "" });

  useEffect(() => { fetch("/api/v1/classes/").then(r => r.json()).then(setClasses).catch(() => {}); }, []);

  async function createClass() {
    const res = await fetch("/api/v1/classes/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (res.ok) { const c = await res.json(); setClasses(cs => [c, ...cs]); setCreating(false); setForm({ name: "", year: "", section: "" }); }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Classes</h2>
        <button onClick={() => setCreating(true)} className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">
          <Plus size={15} /> New Class
        </button>
      </div>

      {creating && (
        <div className="glass p-5 space-y-3">
          <h3 className="font-semibold text-white">Create Class</h3>
          {[["name","Class Name *"],["year","Academic Year"],["section","Section"]].map(([k,l]) => (
            <div key={k}>
              <label className="text-xs text-[var(--cyrus-muted)] mb-1 block">{l}</label>
              <input className="w-full px-3 py-2 bg-[var(--cyrus-bg)] border border-[var(--cyrus-border)] rounded-lg text-sm focus:outline-none focus:border-violet-600 text-white"
                value={(form as any)[k]} onChange={e => setForm(f => ({...f, [k]: e.target.value}))} />
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button onClick={createClass} className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors">Create</button>
            <button onClick={() => setCreating(false)} className="px-4 py-2 border border-[var(--cyrus-border)] rounded-lg text-sm transition-colors hover:border-violet-600/50">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {classes.length === 0 && <p className="text-[var(--cyrus-muted)] text-sm text-center py-12">No classes yet. Create one above.</p>}
        {classes.map(cls => (
          <Link key={cls.id} href={`/classes/${cls.id}`}>
            <div className="glass p-4 flex items-center gap-4 hover:border-violet-600/40 transition-all cursor-pointer">
              <div className="w-10 h-10 rounded-xl bg-violet-600/20 flex items-center justify-center">
                <GraduationCap size={18} className="text-violet-400" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-white">{cls.name}</p>
                <p className="text-xs text-[var(--cyrus-muted)]">{cls.year && `${cls.year}`}{cls.section && ` · Section ${cls.section}`}</p>
              </div>
              <ChevronRight size={16} className="text-[var(--cyrus-muted)]" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
