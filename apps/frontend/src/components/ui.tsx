import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type PropsWithChildren,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import clsx from "clsx";

export function Shell({ children }: PropsWithChildren) {
  return <div className="min-h-screen bg-transparent text-slate-100">{children}</div>;
}

export function Page({
  title,
  subtitle,
  actions,
  children,
}: PropsWithChildren<{ title: string; subtitle?: string; actions?: ReactNode }>) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 shadow-glow backdrop-blur">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 inline-flex rounded-full border border-orange-400/30 bg-orange-500/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-orange-200">
              HSE CASE AI
            </div>
            <h1 className="font-display text-3xl font-semibold">{title}</h1>
            {subtitle ? <p className="mt-2 max-w-3xl text-sm text-slate-300">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
        </div>
      </div>
      {children}
    </div>
  );
}

export function Card({
  title,
  children,
  className,
}: PropsWithChildren<{ title?: string; className?: string }>) {
  return (
    <section className={clsx("rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-xl", className)}>
      {title ? <h2 className="mb-4 text-lg font-semibold">{title}</h2> : null}
      {children}
    </section>
  );
}

export function Button({
  children,
  className,
  ...props
}: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) {
  return (
    <button
      className={clsx(
        "rounded-2xl border border-orange-400/50 bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  className,
  ...props
}: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) {
  return (
    <button
      className={clsx(
        "rounded-2xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export const TextField = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextField({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        {...props}
        className={clsx(
          "w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm outline-none ring-0 placeholder:text-slate-500 focus:border-orange-400",
          className,
        )}
      />
    );
  },
);

export const TextArea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextArea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      {...props}
      className={clsx(
        "min-h-32 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm outline-none ring-0 placeholder:text-slate-500 focus:border-orange-400",
        className,
      )}
    />
  );
});

export function Badge({ children, tone = "default" }: PropsWithChildren<{ tone?: "default" | "success" | "warn" }>) {
  const styles = {
    default: "border-white/15 bg-white/5 text-slate-200",
    success: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
    warn: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  }[tone];
  return <span className={clsx("rounded-full border px-2.5 py-1 text-xs", styles)}>{children}</span>;
}
