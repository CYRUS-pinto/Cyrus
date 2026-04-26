/**
 * Cyrus — Update sidebar with all Sprint 1-7 routes
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, BookOpen, GraduationCap,
  Upload, CheckSquare, Share2, Settings, Zap,
  Key, Brain
} from "lucide-react";

const navItems = [
  { href: "/dashboard",    label: "Dashboard",    icon: LayoutDashboard },
  { href: "/classes",      label: "Classes",      icon: GraduationCap },
  { href: "/exams",        label: "Exams",        icon: BookOpen },
  { href: "/answer-key",   label: "Answer Key",   icon: Key },
  { href: "/upload",       label: "Upload",       icon: Upload },
  { href: "/grade",        label: "Grade",        icon: CheckSquare },
  { href: "/share",        label: "Share",        icon: Share2 },
  { href: "/adaptive",     label: "Adaptive AI",  icon: Brain },
];

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      {/* ─── Sidebar ─────────────────────────────── */}
      <aside className="w-64 flex-shrink-0 border-r border-[var(--cyrus-border)] bg-[var(--cyrus-surface)] flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-[var(--cyrus-border)]">
          <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center glow">
            <Zap size={16} className="text-white" />
          </div>
          <span className="text-lg font-bold gradient-text">Cyrus</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-0.5">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link key={href} href={href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  active
                    ? "bg-violet-600/20 text-violet-300 border border-violet-600/30"
                    : "text-[var(--cyrus-muted)] hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon size={17} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--cyrus-border)]">
          <div className="flex items-center gap-2 text-xs text-[var(--cyrus-muted)]">
            <div className="w-2 h-2 rounded-full bg-emerald-400 sync-pulse" />
            <span>Offline-ready · Open Source</span>
          </div>
        </div>
      </aside>

      {/* ─── Main content ─────────────────────────── */}
      <main className="flex-1 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-[var(--cyrus-border)] bg-[var(--cyrus-bg)]/80 backdrop-blur sticky top-0 z-10">
          <h1 className="text-base font-semibold text-white">
            {navItems.find(n => pathname === n.href || pathname.startsWith(n.href + "/"))?.label ?? "Cyrus"}
          </h1>
          <div className="flex items-center gap-3 text-xs text-[var(--cyrus-muted)]">
            <a href="http://localhost:8000/docs" target="_blank" className="hover:text-white transition-colors">API Docs ↗</a>
            <a href="https://github.com/cyrus-ai/cyrus" target="_blank" className="hover:text-white transition-colors">GitHub ↗</a>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 p-6 page-enter">
          {children}
        </div>
      </main>
    </div>
  );
}
