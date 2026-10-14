import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Button } from "./button";
import { EmptyState, ErrorState, ProgressSteps } from "./states";

const html = (el: React.ReactElement) => renderToStaticMarkup(el);

describe("Button", () => {
  it("is a plain button by default, so it never submits a form by accident", () => {
    expect(html(<Button>Save</Button>)).toContain('type="button"');
    expect(html(<Button type="submit">Save</Button>)).toContain('type="submit"');
  });

  it("says what is missing when disabled with a reason, and keeps its label otherwise", () => {
    const blocked = html(<Button disabled disabledReason="Add a topic to continue">Create post</Button>);
    expect(blocked).toContain("Add a topic to continue");
    expect(blocked).not.toContain("Create post");
    expect(blocked).toContain("disabled");
    expect(html(<Button disabledReason="Add a topic to continue">Create post</Button>)).toContain("Create post");
  });

  it("keeps its label while loading, blocks clicks and says it is busy", () => {
    const busy = html(<Button loading>Saving</Button>);
    expect(busy).toContain("Saving");
    expect(busy).toContain('aria-busy="true"');
    expect(busy).toContain("disabled");
  });
});

describe("screen states", () => {
  it("an empty state offers the next action", () => {
    const out = html(<EmptyState title="No posts yet" body="Write your first one." action={<Button>Write a post</Button>} />);
    expect(out).toContain("No posts yet");
    expect(out).toContain("Write a post");
  });

  it("an error state is announced and offers a retry", () => {
    const out = html(<ErrorState message="We couldn't load your posts." onRetry={() => {}} />);
    expect(out).toContain('role="alert"');
    expect(out).toContain("Try again");
  });

  it("progress steps mark the first step as in progress", () => {
    const out = html(<ProgressSteps title="Writing your post" steps={["Reading your notes", "Drafting"]} />);
    expect(out).toContain('aria-current="step"');
    expect(out).toContain("(in progress)");
  });
});
