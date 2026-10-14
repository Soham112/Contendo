"use client";

import { useMemo, useState } from "react";
import { usePreviewAuthor } from "@/hooks/usePreviewAuthor";
import { pastedText } from "@/lib/post-text";
import PostPreview from "./PostPreview";
import { Button } from "@/components/ui/button";

/** The preview under the editor: the post as it will appear once copied or published. */
export default function PostPreviewPanel({ content }: { content: string }) {
  const author = usePreviewAuthor();
  const [open, setOpen] = useState(true);
  const text = useMemo(() => pastedText(content), [content]);
  if (!text.trim()) return null;

  return (
    <section aria-labelledby="post-preview-heading" className="w-full rounded-lg bg-surface-container-low px-4 py-5 sm:px-6">
      <div className="flex items-center justify-between gap-4">
        <h3 id="post-preview-heading" className="font-headline text-[1.125rem] text-on-surface">
          Preview
        </h3>
        <Button
          variant="tertiary"
          size="sm"
          aria-expanded={open}
          aria-controls="post-preview-body"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide" : "Show"}
        </Button>
      </div>
      {open && (
        <div id="post-preview-body" className="mt-4">
          <PostPreview text={text} author={author} />
        </div>
      )}
    </section>
  );
}
