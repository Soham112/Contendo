from typing import Any, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Inputs
    topic: str
    format: str
    tone: str
    length: str  # "concise" | "standard" | "long-form" — defaults to "standard" at runtime
    context: Optional[str]
    quality: str  # "draft" | "standard" | "polished" — defaults to "standard" at runtime
    user_id: str  # authenticated user; every store call is scoped by it
    # Which pipeline ran: "A" | "B" | "C" | "B-Opus" (config.features.PIPELINE_VARIANTS),
    # set by run_pipeline. Persisted in generation_traces.node_outputs.
    variant: str
    # The model each single-writer role uses in this run, {draft, review, small}
    # (llm.models.role_models). Absent under A, whose agents use fixed models.
    models: dict[str, str]

    # Loaded profile
    profile: dict[str, Any]

    # Retrieved knowledge
    retrieval_query: str            # exact query string sent to retrieval (topic + context)
    retrieval_path: str             # "hybrid" | "flat_fallback"
    retrieval_confidence: str       # "low" | "medium" | "high" — computed after retrieval
    retrieved_chunk_count: int      # count of chunks actually retrieved
    retrieved_chunks: list[str]       # flat list of "[source_type: X] text" strings — always set for backward compat
    retrieval_bundle: dict            # structured hierarchical bundle {chunks, source_contexts, topic_contexts}
    retrieved_context: str            # pre-formatted text block for draft prompt injection; "" triggers flat fallback
    has_chunks: bool                  # set by retrieval_node: whether any relevant chunk was found
    # Coverage gate set by retrieval_node: {decision: "pass" | "low_coverage" |
    # "bypassed", top_cosine, top_bm25_norm, min_cosine, min_bm25_norm,
    # closest_sources: [{title, preview, similarity}]}. "low_coverage" ends the
    # pipeline before drafting. Persisted in generation_traces.node_outputs.
    coverage_gate: dict[str, Any]
    # Request flag: skip the coverage gate and draft without specifics
    # (no numbers, dates, names, incidents or results unless in topic/context).
    no_specifics: bool

    # Phase 4: user's experience nodes loaded at retrieval time for attribution context
    experience_nodes: list[dict[str, Any]]

    # Previously posted topics (for novelty injection in draft)
    posted_topics: list[str]

    # True when this is the user's very first generated post (no prior history)
    first_post: bool

    # Set once by plan_node (after retrieval); every later node reads these.
    # length_target: {min_words, max_words, may_expand, basis} from
    # utils.formatters.resolve_length_target, or None for threads. basis is
    # "length_setting" | "first_post" | "thin_sources".
    length_target: Optional[dict[str, Any]]
    # perspective: "experience" | "learned" | "opinion" | "mixed", from the
    # chunks' authorship (utils.frames.decide_perspective).
    perspective: str
    # How the archetype was chosen (agents.archetype_agent.choose_archetype):
    # {archetype, chosen, allowed, event_note, event_quote, downgraded_from, reason}.
    archetype_decision: dict[str, Any]

    # Generation state
    # The knowledge-base block exactly as the drafter saw it (frame headers and
    # chunks). Persisted in generation_traces.node_outputs.
    draft_frame_block: str
    current_draft: str
    iterations: int
    archetype: str  # post archetype key from utils.formatters.ARCHETYPES, e.g. "general"
    critic_brief: dict  # diagnosis from critic_node; {} if skipped (draft mode); {"error": ...} if the critic failed
    # One {node, iteration, text} entry each time a node rewrites current_draft
    # (draft, humanizer, predictability_audit, word_count_enforcer). Skipped and
    # no-op runs add nothing. Persisted in generation_traces.
    draft_history: list[dict[str, Any]]
    # One entry per humanizer / predictability_audit run whose output added or
    # changed a fact (number, date, duration, ...) not in its input, the chunks
    # or the profile: {node, iteration, first_attempt, retry, outcome}, where
    # outcome is "accepted_after_retry" or "reverted". Persisted in
    # generation_traces.node_outputs.
    specifics_guard: list[dict[str, Any]]

    # Single-writer drafting (variants B and C only; absent under A).
    # source_index: S-id -> {position, chunk_id, frame, authorship}, as the
    #   drafter's sources block numbered the chunks (utils.frames.build_sources_block).
    # event: what the draft's <event> part said, {status, source, quote, line}
    #   (utils.draft_output.DraftOutput; status "absent" for a non-story post).
    # draft_format: what broke a draft's output envelope, [{draft, kind, text}]
    #   (text outside the tags, a missing or unclosed <post>, a second <event>);
    #   set only when something did. Text outside the tags never reaches the post.
    # citations: the post's spans, [{start, end, text, basis, sources}], offsets
    #   into the post without markers. One per sentence once variant B has
    #   fixed anything (pipeline.fixes).
    # citation_failures: marker-like text that is not a usable citation,
    #   [{kind, text, start, end}], offsets into the marked draft's body.
    # All are persisted in generation_traces.node_outputs; the draft as the
    # model wrote it, envelope included, is the "draft" entry in draft_history.
    source_index: dict[str, dict[str, Any]]
    event: dict[str, Any]
    draft_format: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    citation_failures: list[dict[str, Any]]
    # multi_sentence_spans: how many spans of the draft hold more than one
    #   sentence (the drafter is asked for a marker per sentence). A metric
    #   only: nothing acts on it.
    multi_sentence_spans: int
    # draft_truncated: set only when the draft stopped at its output limit,
    #   {max_tokens, output_tokens}; the run then returns no post.
    # draft_refused: set only when the model declined to write the draft
    #   (stop_reason "refusal"), {category}; the run then returns no post.
    # trim_result: set only when the post was over its maximum and the trim ran,
    #   {outcome: trimmed | trim_failed, reason, max_words, words_before,
    #    words_after, ranking, deleted, kept_ranked}: the model's ranking of
    #    expendable sentences, those deleted, and those ranked but not needed.
    #    Each is [{index, span, text}]: index is the sentence's position among
    #    the post's sentences, span the position of the span it was in
    #    (agents.trim_agent.trim_node).
    draft_truncated: dict[str, Any]
    draft_refused: dict[str, Any]
    trim_result: dict[str, Any]
    # The deterministic checks (pipeline.checks), each {issues: [{type, span,
    # text, sources, detail}], counts: {type: n}}. checks_before_trim is on the
    # finalised draft; checks_final is on the post that is returned (the same
    # result when no trim ran). After a redraft (variant B) both are the
    # redraft's; the first draft's checks are then in review["first"]["checks"].
    checks_before_trim: dict[str, Any]
    checks_final: dict[str, Any]

    # Variant B only (absent under A and C, and under B with quality="draft").
    # review_first, review_second: the structured review of the first draft and
    #   of the post after the fixes or the full redraft
    #   (agents.review_agent.review_post): {outcome, issues, invalid,
    #   unreviewed, records, sentences, reused, reviewed, groups, model,
    #   input_tokens, output_tokens, error?}. The second sends only the
    #   sentences a model wrote since; reused / reviewed count both kinds.
    # review: what was done about the issues (pipeline.redraft, pipeline.fixes):
    #   {first: {checks, acting, recorded},
    #    fixes: {code: [{type, issue, sentence, before, after}], origin,
    #            unplaced, route: none | targeted | full}   when anything acted
    #    targeted: {entries, flagged, parts, answer, applied, unchanged, invalid,
    #               format_failures, input_tokens, output_tokens}   targeted path only
    #    redraft: {entries, downgraded_from?, input_tokens, output_tokens}   full path only
    #    redraft_truncated: {max_tokens, output_tokens}   only when the full
    #              redraft was cut off; the post is then returned as it was
    #    redraft_refused: {category}   only when the model declined the full
    #              redraft; the post is then returned as it was
    #    fixes_after_redraft: {code, origin}   full path only, when code fixed
    #              something on the redraft after its review
    #    second: {checks, acting, recorded}            when anything acted
    #    removed: [{kind, text, how: deleted | trimmed, by: code | model}],
    #    remaining: acting issues on the returned post,
    #    unreviewed: sentences of the returned post with no valid review record,
    #    outcome: clean | fixed | issues_remain | not_reviewed}
    # step_timings: [{step, seconds}], one per graph step that ran, in order.
    review_first: dict[str, Any]
    review_second: dict[str, Any]
    review: dict[str, Any]
    step_timings: list[dict[str, Any]]

    # The validation record of the returned post (pipeline.finalise), all
    # variants: {words, target, length: ok | over_length | under_length |
    # no_target, over_by, under_by, leftover_markers, em_dashes_remaining}.
    # Pipeline A is recorded only: its post is never changed by it.
    final_validation: dict[str, Any]

    # Final fact check (fact_check_node): {flagged: [{i, sentence, type, why}],
    # rewrites: [{sentence, type, why, rewrite, recheck, outcome}],
    # outcome, error?}. Persisted in generation_traces.node_outputs.
    fact_check: dict[str, Any]

    # Scoring
    score: int
    score_error: bool  # the last scorer run returned no valid score
    score_feedback: list[str]
    score_history: list[dict[str, Any]]  # one {iteration, score, score_feedback} per scorer run

    # Final output
    final_post: str
