"use client";

// A modal dialog (Radix Dialog: focus trap, Escape to close, labelled by its
// title), faded and lifted in with Motion.

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { transition } from "./motion";

export function Dialog({
  open, onOpenChange, title, description, children, className, hideClose = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Read out with the title; also shown under it. */
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  /** For dialogs that must be answered with one of their own buttons. */
  hideClose?: boolean;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-[200] bg-on-surface/30"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition.fast}
              />
            </DialogPrimitive.Overlay>
            {/* Centred by flex, since Motion owns the dialog's transform. */}
            <div className="pointer-events-none fixed inset-0 z-[201] flex items-center justify-center p-4">
              <DialogPrimitive.Content asChild forceMount>
                <motion.div
                  className={cn(
                    "pointer-events-auto relative w-full max-w-lg",
                    "rounded-2xl bg-surface-container-lowest p-6 sm:p-8 shadow-ambient focus:outline-none",
                    "max-h-[calc(100vh-2rem)] overflow-y-auto",
                    className
                  )}
                  initial={{ opacity: 0, y: 8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.98 }}
                  transition={transition.base}
                >
                  <DialogPrimitive.Title className="font-headline text-[1.375rem] leading-snug text-on-surface pr-8">{title}</DialogPrimitive.Title>
                  {description ? (
                    <DialogPrimitive.Description className="mt-2 text-[0.9375rem] leading-relaxed text-on-surface-variant">
                      {description}
                    </DialogPrimitive.Description>
                  ) : (
                    <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
                  )}
                  {children && <div className="mt-6">{children}</div>}
                  {!hideClose && (
                    <DialogPrimitive.Close
                      className="absolute right-3 top-3 grid h-11 w-11 place-items-center rounded-md text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      aria-label="Close"
                    >
                      <X size={18} aria-hidden="true" />
                    </DialogPrimitive.Close>
                  )}
                </motion.div>
              </DialogPrimitive.Content>
            </div>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  );
}

/** A row of dialog buttons, primary action last (right on desktop, top on phones). */
export function DialogActions({ children }: { children: React.ReactNode }) {
  return <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">{children}</div>;
}
