"use client";

import * as React from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange: (open: boolean) => void; children: React.ReactNode }) {
  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onOpenChange(false);
      }
    }

    if (open) {
      window.addEventListener("keydown", onKeyDown);
      return () => window.removeEventListener("keydown", onKeyDown);
    }
  }, [open, onOpenChange]);

  if (!open) {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 cursor-default bg-slate-950/45 backdrop-blur-[1px]"
        onClick={() => onOpenChange(false)}
      />
      {children}
    </div>,
    document.body
  );
}

function DialogContent({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("relative z-10 w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl", className)}>{children}</div>;
}

function DialogHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("space-y-2", className)}>{children}</div>;
}

function DialogTitle({ className, children }: { className?: string; children: React.ReactNode }) {
  return <h2 className={cn("text-xl font-semibold text-slate-950", className)}>{children}</h2>;
}

function DialogDescription({ className, children }: { className?: string; children: React.ReactNode }) {
  return <p className={cn("text-sm leading-6 text-slate-600", className)}>{children}</p>;
}

function DialogFooter({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end", className)}>{children}</div>;
}

export { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle };