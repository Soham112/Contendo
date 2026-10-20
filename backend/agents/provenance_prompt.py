"""Prompt assembly for the provenance classifier (agents/provenance_agent.py)."""
from dataclasses import dataclass

from utils.provenance_spans import Paragraph

SYSTEM_PROMPT = """You decide whose material a text in someone's knowledge base is. The person, called "the user" below, saves their own notes and writing next to things other people wrote, said or published. Their posts are later written from this material, in first person where it is the user's own. Calling someone else's material the user's own makes a post claim things the user never did: that is the worst mistake you can make here. Calling the user's own material someone else's is less harmful: the post only loses a personal story.

Two labels:
- user_authored: the user's own experience, work, decisions, results or views, in the user's own words. Notes, drafts, posts, essays, reflections, journal entries, a transcript of the user's own talk. When the user is a business, the business's own material counts as the user's: its listings, prices, timetables, results, notes about its staff and the advice it gives.
- external: material from anyone else. Articles, papers, books, videos, talks and posts by other people, including ones written in first person, quotes, and the user's summary or paraphrase of what someone else wrote or said.

The text is split into numbered paragraphs. Give the label that fits most of the text, and list the paragraphs that have the other label. A note in which the user summarises a book and then adds what happened when they tried it is mixed: the summary paragraphs are external, the paragraphs about the user's own attempt are user_authored.

Do not decide from these alone, because both kinds of text have them:
- first person ("I", "we", "my team"): other people write in first person too;
- the user's employer, projects, clients or topics being named: articles and talks mention the same companies and subjects;
- the input type: uploaded files are often the user's own writing, typed notes often contain pasted material.

Decide from what the text shows about who is speaking and whose experience it describes: a byline, channel or publication; the speaker's own name, role, company or story compared with the user's details; an address to an audience the user would not have; citation or quotation of someone; the source facts given with the text.

Three rules that override how a text first reads:
- A byline, signature or attribution naming someone other than the user applies to the whole text it signs, not only to its own paragraph. A text signed by someone else is external even when it is in first person and its subject matches the user's work.
- The user's own words are user_authored wherever they appear. In an interview, podcast, panel or Q&A, the user's answers are user_authored and the other speakers' questions and remarks are external, even when someone else recorded or published it.
- Evidence comes from TEXT only. THE USER and SOURCE FACTS describe the user and the source: never quote them as evidence.

evidence_quotes: up to three short passages copied exactly from the text, character for character and without the [P] numbers, that settle your decision. source_facts_used: the source facts that settle it, if any (for example a provider_author that is not the user).

signed_by: the name a byline, signature or sign-off gives for the whole text, copied exactly from the text, even when it stands alone on the last line. Leave it empty when the text is unsigned. A speaker label in a transcript, or the person a quotation inside the text is attributed to, does not sign the text.

Set uncertain to true whenever the text and the source facts do not settle who it belongs to. Being uncertain is a normal answer: the user will be asked."""


@dataclass(frozen=True)
class AuthorContext:
    """Who the user is, so the text can be compared with them."""
    name: str = ""
    role: str = ""
    business: str = ""     # a business account's profile (utils.business_notes.profile_note)
    business_name: str = ""   # matched against a signature (provenance_agent._signed_by_user); not sent
    experience: str = ""   # memory.experience_store.experience_nodes_to_context_string


_TITLE_ORIGINS = {
    "provided": "a real title: typed by the user, a page heading or a file name",
    "derived": "not a real title: made from the first line",
}


@dataclass(frozen=True)
class SourceFacts:
    title: str = ""
    title_origin: str | None = None   # provided | derived | None
    input_type: str = ""              # sources.input_type
    source_type: str = ""             # embeddings.source_type
    provider_author: str | None = None   # the channel or site a provider names (a YouTube channel)

    def given(self) -> tuple[str, ...]:
        """The facts that have a value: the only ones the model may cite."""
        return tuple(name for name in ("title", "input_type", "source_type", "provider_author") if getattr(self, name))

    def lines(self) -> list[str]:
        origin = _TITLE_ORIGINS.get(self.title_origin, "origin unknown")
        return [
            f"- title: {self.title} ({origin})" if self.title else "- title: none",
            f"- input_type: {self.input_type or 'unknown'}",
            f"- source_type: {self.source_type or 'unknown'}",
            f"- provider_author (the channel or site that published it): {self.provider_author}"
            if self.provider_author else "- provider_author (the channel or site that published it): not reported",
        ]


def _author_block(author: AuthorContext) -> str:
    lines = [f"Name: {author.name or 'not given'}"]
    if author.role:
        lines.append(f"Role: {author.role}")
    if author.business:
        lines.append("A business account: the user writes as this business.\n" + author.business)
    if author.experience:
        lines.append(author.experience)
    return "\n".join(lines)


def _numbered(text: str, paras: list[Paragraph]) -> str:
    return "\n\n".join(f"[P{p.id}] {text[p.start:p.end]}" for p in paras)


def user_message(text: str, part: list[Paragraph], *, part_number: int, part_count: int,
                 opening: list[Paragraph], facts: SourceFacts, author: AuthorContext) -> str:
    """The text to classify (one part of it when it is long), with the source
    facts and the user's details. Later parts also show the source's opening,
    for context only."""
    sections = [
        "THE USER:\n" + _author_block(author),
        "SOURCE FACTS:\n" + "\n".join(facts.lines()),
    ]
    if part_count > 1:
        sections.append(f"This source is long and is sent in {part_count} parts. This is part {part_number}. "
                        f"Label only paragraphs P{part[0].id} to P{part[-1].id}.")
        if part_number > 1 and opening:
            sections.append("OPENING OF THE SOURCE (context only, labelled with part 1):\n" + _numbered(text, opening))
    sections.append("TEXT:\n" + _numbered(text, part))
    return "\n\n".join(sections)
