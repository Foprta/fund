"""Fail-closed contract for the tracked (public) build.

With no local mechanism module installed, the assistant must grant nothing
beyond research: the access decision denies all fund tools, no canned
deflection or prompt addendum is produced, and the tracked code carries no
access-mechanism strings. This test must pass WITHOUT any local module.
"""

import api.access as access
import api.agent as agent
import api.policy as policy
import api.tools as tools


def _local_absent() -> bool:
    return getattr(policy, "_impl", None) is None


def test_access_decision_denies_everything_when_unconfigured():
    if not _local_absent():
        # A local mechanism is installed in this checkout; the public contract
        # is only meaningful without it. Skip rather than assert the opposite.
        import pytest

        pytest.skip("local mechanism module present in this checkout")

    for q in [
        "what is the fund NAV?",
        "show me the holdings",
        "give me the breakdown by person",
        "how do I get more access?",
        "hello",
    ]:
        d = policy.access_decision(q, None)
        assert d == access.DENY_ALL
        assert d.canned_reply is None
        assert d.allow_fund_tools is False
        assert d.allow_participant_lookup is False
        assert d.prompt_addendum == ""


def test_deny_all_builds_research_only_tools():
    import pytest

    if getattr(tools, "_tools_local", None) is not None:
        pytest.skip("local tools module present in this checkout")

    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    session = MagicMock(spec=AsyncSession)
    # Even if a caller passes the flags, with no local module the lookup tool
    # cannot materialize.
    built = tools.build_luna_tools(
        session, include_fund_data=False, include_participant_lookup=True
    )
    names = {t.name for t in built}
    # Only research is reachable in the public build.
    assert names <= {"search_research"}


def test_deny_all_prompt_has_no_restricted_language():
    """The public build's prompt must not contain any restricted vocabulary.

    The forbidden terms are loaded from an optional local list when present; the
    public build keeps none of them in source. (b"..." keeps the literals out of
    plain tracked text.)
    """
    prompt = agent.build_system_prompt(access.DENY_ALL).lower()
    # Base check: a couple of generic, non-revealing tokens.
    for token in (b"per-person", b"member list"):
        assert token.decode() not in prompt

    try:
        from restricted_terms_local import RESTRICTED_TERMS
    except ImportError:
        RESTRICTED_TERMS = ()
    for term in RESTRICTED_TERMS:
        assert term not in prompt, "public prompt leaks a restricted term"
