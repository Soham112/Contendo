"""The prompt for a selection refine of a single-writer post (one whose
generation trace stored a source index). The call, the checks and the retry are
in agents/refine_agent.py, which also holds the prompt for posts that have no
source index (pipeline A's).

It is put together from the blocks the single-writer drafter is given, so the
rewritten passage is held to the same rules as the post it sits in: the style
rules (utils.formatters.STYLE_RULES), the delimited sources block and the
sources-are-data rule (utils.frames), and the citation rules
(agents.draft_prompt.CITATION_RULES).
"""

from agents.draft_prompt import CITATION_RULES
from agents.redraft_prompt import NEVER_ADD, QUOTED_MATERIAL, format_problems
from utils.formatters import STYLE_RULES
from utils.frames import SOURCES_ARE_DATA_RULE

REFINE_CITED_PROMPT = """You are editing one selected section of a post. You may change its wording, structure and emphasis. You may not change what it claims.

Author voice (voice and style only; never a source of content, stories or facts):
{profile_context}

{business_facts}Sources (what the author's knowledge base held when the post was written):
""" + SOURCES_ARE_DATA_RULE + """
{sources_block}

Topic the post was written on: {topic}
{context_line}
Full post (for voice and context only; do NOT rewrite it, and do not treat it as a source):
<post>
{full_post}
</post>

Selected section to rewrite:
<selection>
{selected_text}
</selection>

Instruction from the author:
<instruction>
{instruction}
</instruction>

---
STYLE RULES (mandatory):
{style_rules}
---

""" + CITATION_RULES + """

In this edit, [[R]] also covers what the author's instruction states: a fact the author gives in the instruction is cited [[R]].

Where facts may come from:
- Every fact, number, date, name and event in your rewrite must be stated by a source, the topic, the context or the author's instruction, and its sentence cites that.
- Never invent an example, anecdote, statistic, name, quote or event, and never write something that only sounds like it happened.
- Keep each source's attribution. Do not present something a source attributes to someone else as the author's own experience.
- If the instruction asks for something none of those contain (for example "add a real example" when no source has one), do not make it up. Make the part of the change you can, keep the section's facts as they are, and end your output with one short note on its own line, in exactly this form:
  <note>what you could not add, and what the author could put in the instruction so you can</note>
- Add a note only in that case.

Rules:
- Rewrite ONLY the selected section according to the instruction.
- Match the voice, tone and style of the surrounding post.
- Do not add line breaks unless the selection had them.
- Keep roughly the same length unless the instruction says otherwise.
- Output ONLY the rewritten section, each sentence ending with its marker (and the note, if one is needed): no explanation, no preamble, no quotes around it.{retry}"""

_RETRY = """

---
YOUR PREVIOUS REWRITE WAS CHECKED AND NOT ACCEPTED.
<previous_rewrite>
{previous}
</previous_rewrite>

<problems>
{problems}
</problems>

Write the section again with those problems fixed.
- Fix each problem by doing what its "What to do" line says, and nothing more.
- """ + NEVER_ADD + """
- """ + QUOTED_MATERIAL + """
---"""


def build_refine_cited_prompt(*, profile_context: str, words_to_avoid: list[str], sources_block: str, topic: str,
                              context: str, full_post: str, selected_text: str, instruction: str,
                              previous: str = "", problems: list[dict] | None = None, empty_retry: bool = False, business: dict | None = None) -> str:
    """The prompt for one attempt. previous and problems (pipeline.redraft
    issue entries for the checks' findings on it) are given on the retry."""
    retry = _RETRY.format(previous=previous, problems=format_problems(problems)) if problems else ""
    if empty_retry:
        retry += "\nYour previous reply contained no rewrite or note. Return the rewritten section or the requested note."
    from agents.draft_prompt import business_facts
    prompt = REFINE_CITED_PROMPT.format(
        business_facts=business_facts({"business": business}),
        profile_context=profile_context,
        sources_block=sources_block,
        topic=topic,
        context_line=f"Additional context given with it: {context}\n" if context.strip() else "",
        full_post=full_post,
        selected_text=selected_text,
        instruction=instruction,
        style_rules=STYLE_RULES.format(words_to_avoid=", ".join(words_to_avoid)),
        retry=retry,
    )

    if business_facts({"business": business}):
        prompt = prompt.replace("- Cite only ids that appear in <sources>, and cite a source only for what that source says.",
                                "- [[B]] cites the BUSINESS FACTS block only. For retrieved sources, cite only ids in <sources> and only what that source says.")
    return prompt
