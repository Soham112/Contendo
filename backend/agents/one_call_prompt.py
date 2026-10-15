"""The one-call draft prompt (variant D): the drafter chooses the structure.

Variant C asks a small model for the structure first (agents/archetype_agent),
then gives the drafter that one structure. Variant D makes one call: the
drafter gets every structure the code allows for these sources
(archetype_agent.structure_offer, the same rule C uses) and names the one it
chose in a <structure> tag before the post. The rest of the prompt is C's
(agents/draft_prompt.render_cited_prompt). pipeline/finalise.read_structure_node
reads the tag and keeps the choice only when it is one of the allowed types.
"""

from agents.draft_prompt import render_cited_prompt
from pipeline.state import PipelineState
from utils.formatters import ARCHETYPES, GENERAL_ARCHETYPE, STORY_ARCHETYPES
from utils.frames import SourcesBlock

_CHOOSE_STRUCTURE = """---
POST STRUCTURE: choose one of these post types and write the post to its structure.
Choose by what the sources can fill, not by how the topic is phrased. Choose "{general}" when no other type clearly fits.
The structure is a shape, not a checklist: leave out any section the sources cannot fill.

{options}{story_rule}
---"""

_OPTION = """<type key="{key}">
{name}: fits {fits}.
{structure}
</type>"""

_STORY_RULE = """

These types tell something that happened to the author: {story_keys}. Choose one only if a source whose kind begins OWN EXPERIENCE describes the event this post is about."""

_EVENT_RULE = """---
EVENT (mandatory when you chose {story_keys}):
Those types tell something that happened to the author. After the <structure> part, you name that event inside <event> tags, in exactly this form:
<event><id of the source that describes the event> | "<one sentence copied word for word from that source, describing the event>"</event>
- The source must be one whose kind begins OWN EXPERIENCE, and the event must be the one the topic is about.
- Copy the sentence exactly: the same words, numbers and punctuation.
For any other type, write no <event> part.
The <event> part is removed before the author sees the post.
---

"""

_OUTPUT_FORMAT = """---
OUTPUT FORMAT (mandatory):
Your whole output is the <structure> part, then the post between <post> and </post>, and nothing else:
<structure><the key of the post type you chose></structure>
<post>
<the post, with its markers>
</post>
Write nothing before <structure>, nothing between </structure> and <post>, and nothing after </post>: no preamble, no explanation, no separator line.
---"""

_OUTPUT_FORMAT_WITH_EVENT = """---
OUTPUT FORMAT (mandatory):
Your whole output is the <structure> part, the <event> part when the EVENT rule asks for one, then the post between <post> and </post>, and nothing else:
<structure><the key of the post type you chose></structure>
<event><only for {story_keys}: as the EVENT rule above says></event>
<post>
<the post, with its markers>
</post>
Write nothing before <structure>, nothing between the parts, and nothing after </post>: no preamble, no explanation, no separator line.
---"""


def build_one_call_prompt(state: PipelineState, allowed: list[str]) -> tuple[str, SourcesBlock]:
    """The variant D draft prompt for the structures in `allowed` (keys of
    utils.formatters.ARCHETYPES, from archetype_agent.structure_offer), and the
    sources block it shows."""
    story_keys = [key for key in allowed if key in STORY_ARCHETYPES]
    listed = ", ".join(story_keys)
    options = "\n".join(
        _OPTION.format(key=key, name=ARCHETYPES[key].name, fits=ARCHETYPES[key].fits,
                       structure=ARCHETYPES[key].structure)
        for key in allowed
    )
    structure = _CHOOSE_STRUCTURE.format(
        general=GENERAL_ARCHETYPE, options=options,
        story_rule=_STORY_RULE.format(story_keys=listed) if story_keys else "",
    )
    return render_cited_prompt(
        state,
        structure=structure,
        event_rule=_EVENT_RULE.format(story_keys=listed) if story_keys else "",
        output_format=_OUTPUT_FORMAT_WITH_EVENT.format(story_keys=listed) if story_keys else _OUTPUT_FORMAT,
    )
