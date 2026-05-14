import { NavLink, Outlet } from "react-router-dom";
import { Shell } from "../components/ui";

const navItems = [
  { to: "/", label: "Проекты" },
  { to: "/providers", label: "Провайдеры" },
  { to: "/mcp", label: "MCP" },
  { to: "/agents", label: "Агенты" },
  { to: "/logs", label: "Логи" },
];

export function AppLayout() {
  return (
    <Shell>
      <div className="border-b border-white/10 bg-slate-950/60 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
          <div>
            <div className="text-xs uppercase tracking-[0.35em] text-orange-300">CASE Platform</div>
            <div className="text-xl font-semibold">Генеративная CASE-система</div>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm ${
                    isActive ? "bg-orange-500 text-white" : "bg-white/5 text-slate-300 hover:bg-white/10"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
      <Outlet />
    </Shell>
  );
}
