"use client";

// App-wide toasts: `const { showToast } = useToast(); showToast("Saved", "success")`.
// Built on Radix Toast (announced to screen readers, F8 jumps to them,
// swipe to dismiss) and animated with Motion.

import React, { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { transition } from "./motion";

export type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);
const DURATION_MS = 4000;

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info };
const STYLES: Record<ToastType, string> = {
  success: "bg-primary text-white",
  error: "bg-error text-white",
  info: "bg-on-surface text-surface-container-lowest",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);
  const remove = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ showToast }}>
      <ToastPrimitive.Provider duration={DURATION_MS} swipeDirection="right">
        {children}
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icon = ICONS[toast.type];
            return (
              <ToastPrimitive.Root
                key={toast.id}
                asChild
                forceMount
                type={toast.type === "error" ? "foreground" : "background"}
                onOpenChange={(open) => { if (!open) remove(toast.id); }}
              >
                <motion.li
                  layout
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 24 }}
                  transition={transition.base}
                  className={cn("pointer-events-auto flex items-center gap-3 rounded-xl px-4 py-3 shadow-float", STYLES[toast.type])}
                >
                  <Icon size={18} aria-hidden="true" className="shrink-0" />
                  <ToastPrimitive.Description className="flex-1 text-[0.875rem] font-medium leading-snug">{toast.message}</ToastPrimitive.Description>
                  <ToastPrimitive.Close aria-label="Dismiss" className="-mr-1 grid h-8 w-8 shrink-0 place-items-center rounded-md opacity-80 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
                    <X size={16} aria-hidden="true" />
                  </ToastPrimitive.Close>
                </motion.li>
              </ToastPrimitive.Root>
            );
          })}
        </AnimatePresence>
        <ToastPrimitive.Viewport className="pointer-events-none fixed bottom-4 right-4 left-4 z-[400] flex flex-col items-stretch gap-3 outline-none sm:left-auto sm:bottom-6 sm:right-6 sm:w-[24rem]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
