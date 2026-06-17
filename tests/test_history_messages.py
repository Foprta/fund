"""_history_to_messages: bare user-only chains must not become unanswered stacks.

When assistant replies are lost (client disconnects before persist), a
conversation's stored history is several user turns in a row. Fed verbatim to
the model, it reads them as a pile of unanswered questions and answers them all
at once. _history_to_messages normalizes such history so the model only ever
sees the current question plus clean user/assistant alternation.
"""

from langchain_core.messages import AIMessage, HumanMessage

from api.graph import _history_to_messages


def _shape(messages):
    return [
        ("user" if isinstance(m, HumanMessage) else "assistant", m.content)
        for m in messages
    ]


def test_empty_history_just_current_message():
    msgs = _history_to_messages([], "привет")
    assert _shape(msgs) == [("user", "привет")]


def test_healthy_alternation_preserved():
    history = [
        ("user", "What are holdings?"),
        ("assistant", "BTC, ETH"),
    ]
    msgs = _history_to_messages(history, "and the total?")
    assert _shape(msgs) == [
        ("user", "What are holdings?"),
        ("assistant", "BTC, ETH"),
        ("user", "and the total?"),
    ]


def test_bare_user_chain_collapses_to_current_question_only():
    """The reported bug: 5 user turns, no assistant → model answered them all."""
    history = [
        ("user", "обьясни как работает курв"),
        ("user", "почему CRV падает?"),
        ("user", "сколько стоит фонд?"),
        ("user", "Поясни за YB"),
        ("user", "Поясни за YB"),
    ]
    msgs = _history_to_messages(history, "привет")
    # Orphan user run merged then dropped; only the current question remains.
    assert _shape(msgs) == [("user", "привет")]


def test_trailing_user_orphan_dropped_but_prior_pair_kept():
    history = [
        ("user", "What is the fund worth?"),
        ("assistant", "$46k"),
        ("user", "lost question"),  # assistant reply never saved
    ]
    msgs = _history_to_messages(history, "new question")
    assert _shape(msgs) == [
        ("user", "What is the fund worth?"),
        ("assistant", "$46k"),
        ("user", "new question"),
    ]


def test_internal_user_run_merged_into_single_turn():
    history = [
        ("user", "first"),
        ("user", "second"),
        ("assistant", "answer to both"),
    ]
    msgs = _history_to_messages(history, "follow up")
    assert _shape(msgs) == [
        ("user", "first\n\nsecond"),
        ("assistant", "answer to both"),
        ("user", "follow up"),
    ]


def test_unknown_roles_ignored():
    history = [("system", "noise"), ("user", "q"), ("assistant", "a")]
    msgs = _history_to_messages(history, "next")
    assert _shape(msgs) == [
        ("user", "q"),
        ("assistant", "a"),
        ("user", "next"),
    ]
