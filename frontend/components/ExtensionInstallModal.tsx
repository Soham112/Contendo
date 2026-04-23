"use client";

interface ExtensionInstallModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDownload: () => void;
}

const EXTENSION_BANNER_DISMISSED_KEY = "contendo_extension_banner_dismissed";

const INSTALL_STEPS = [
  'Click "Download Extension" below',
  "Unzip the downloaded folder",
  "Open chrome://extensions in a new tab",
  'Enable "Developer mode" (toggle, top right)',
  'Click "Load unpacked" and select the unzipped folder',
];

export default function ExtensionInstallModal({
  isOpen,
  onClose,
  onDownload,
}: ExtensionInstallModalProps) {
  if (!isOpen) return null;

  const handleDownloadClick = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem(EXTENSION_BANNER_DISMISSED_KEY, "1");
    }
    onDownload();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(47,51,51,0.35)", backdropFilter: "blur(4px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-surface-container-lowest rounded-2xl px-8 py-7 w-full max-w-lg mx-4"
        style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.08), 0px 24px 60px rgba(47,51,51,0.12)" }}
      >
        <h2 className="font-headline text-[1.7rem] text-on-surface leading-tight">
          Install Contendo for Chrome
        </h2>
        <p className="mt-2 text-[13px] text-secondary leading-relaxed">
          Add anything to memory without leaving your browser - YouTube videos, articles, and URLs in one click.
        </p>

        <ol className="mt-6 space-y-3">
          {INSTALL_STEPS.map((step, idx) => (
            <li key={step} className="flex gap-3 items-start">
              <span className="text-primary text-[13px] font-semibold min-w-5 leading-6">{idx + 1}.</span>
              <span className="text-[13px] text-on-surface leading-6">{step}</span>
            </li>
          ))}
        </ol>

        <p className="mt-5 text-[12px] text-outline">Works on Chrome, Brave, and Edge</p>

        <div className="mt-7 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-[13px] text-secondary hover:text-on-surface transition-colors rounded-xl"
          >
            Close
          </button>
          <a
            href="https://github.com/Soham112/Contendo/releases/download/v1.0.0-extension/contendo-extension.zip"
            download
            onClick={handleDownloadClick}
            className="btn-primary px-5 py-2 text-[13px] text-white rounded-xl font-semibold hover:opacity-90 transition-opacity"
          >
            Download Extension
          </a>
        </div>
      </div>
    </div>
  );
}
