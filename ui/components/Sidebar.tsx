"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Wand2, ListChecks, Key, Github } from "lucide-react";

const links = [
  { href: "/",         label: "Dashboard",  icon: LayoutDashboard },
  { href: "/generate", label: "Generate",   icon: Wand2 },
  { href: "/tasks",    label: "Tasks",      icon: ListChecks },
  { href: "/keys",     label: "API Keys",   icon: Key },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-zinc-800 flex flex-col py-6 px-3 gap-1">
      <div className="px-3 mb-6">
        <span className="text-xl font-bold tracking-tight text-indigo-400">OpenSway</span>
        <p className="text-xs text-zinc-500 mt-0.5">Open Source Media AI</p>
      </div>
      {links.map(({ href, label, icon: Icon }) => {
        const active = path === href || (href !== "/" && path.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors
              ${active
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              }`}
          >
            <Icon size={16} />
            {label}
          </Link>
        );
      })}
      <div className="mt-auto px-3">
        <a
          href="https://github.com/your-org/opensway"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <Github size={14} /> View on GitHub
        </a>
      </div>
    </aside>
  );
}
