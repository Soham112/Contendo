"""same_wording(): forms English fixes are the same wording; anything else differs."""

import pytest

from utils.wording import same_wording


@pytest.mark.parametrize("first,second", [
    ("nine", "9"), ("Nine steps", "9 steps"), ("one outcome", "1 outcome"), ("twenty-five", "25"),
    ("four hundred and ten thousand", "410,000"), ("38 percent", "thirty eight percent"),
    ("didn't", "did not"), ("What didn't help", "what did not help"), ("can't", "cannot"), ("won't", "will not"),
    ("we're", "we are"), ("I've", "I have"), ("it's", "it is"), ("it's", "it has"), ("they'd", "they would"),
    ("they'd", "they had"), ("I’m", "I am"), ("Early   meetings", "early meetings"), ("the team's plan", "the team's plan"),
])
def test_forms_fixed_by_the_language_are_the_same_wording(first, second):
    assert same_wording(first, second) and same_wording(second, first)


@pytest.mark.parametrize("first,second", [
    ("Early meetings", "first board meetings"), ("nine", "eight"), ("38 percent", "61 percent"),
    ("nobody maintains", "nobody updates"),                    # a synonym is still a difference here
    ("did not", "did"), ("it is", "it was"), ("the team's plan", "the team is plan" + "s"),
    ("March", "April"), ("a third", "33 percent"), ("", "nine"),
])
def test_anything_else_is_a_difference(first, second):
    assert not same_wording(first, second)
