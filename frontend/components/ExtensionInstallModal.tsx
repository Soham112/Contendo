"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogActions } from "@/components/ui/dialog";

interface ExtensionInstallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const INSTALL_STEPS = [
  'Click "Download Extension" and save to your Downloads folder',
  "Find the zip in Downloads and unzip it (double-click on Mac, right-click → Extract All on Windows)",
  "Open chrome://extensions in a new tab",
  'Enable "Developer mode" (toggle, top right)',
  'Click "Load unpacked" and select the unzipped folder',
];

export default function ExtensionInstallModal({
  isOpen,
  onClose,
}: ExtensionInstallModalProps) {
  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => { if (!open) onClose(); }}
      title="Install Contendo for Chrome"
      description="Add YouTube videos, articles and links to your library without leaving your browser."
    >
      <ol className="space-y-3">
        {INSTALL_STEPS.map((step, idx) => (
          <li key={step} className="flex gap-3 items-start">
            <span className="text-primary text-[0.875rem] font-semibold min-w-5 leading-6">{idx + 1}.</span>
            <span className="text-[0.875rem] text-on-surface leading-6">{step}</span>
          </li>
        ))}
      </ol>
      <p className="mt-5 text-[0.8125rem] text-on-surface-variant">Works on Chrome, Brave and Edge.</p>
      <DialogActions>
        <Button variant="secondary" onClick={onClose}>Close</Button>
        <Button asChild>
          <a href="https://github.com/Soham112/Contendo/releases/download/v1.0.0-extension/contendo-extension.zip" download>
            Download the extension
          </a>
        </Button>
      </DialogActions>
    </Dialog>
  );
}
