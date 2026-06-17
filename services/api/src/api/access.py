"""Neutral access-decision contract shared by the policy loader and the agent.

This module names no access tiers and no mechanism. It only describes, for a
given request, what the assistant is allowed to do: which (if any) canned reply
to emit, whether fund/portfolio tools may be bound, and an optional extra prompt
fragment. The actual decision logic lives in a local, gitignored module when
present; otherwise the fail-closed default below denies all fund access.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessDecision:
    # If set, the pipeline emits this text verbatim and binds no tools.
    canned_reply: str | None = None
    # Whether fund summary / holdings tools may be exposed to the model.
    allow_fund_tools: bool = False
    # Whether the optional local detail-lookup tools may be exposed.
    allow_detail_lookup: bool = False
    # Extra system-prompt fragment (empty in the fail-closed build).
    prompt_addendum: str = ""


# Fail-closed default: no fund data, no canned deflection, no extra prompt.
# Research-only access is all the tracked build can ever grant.
DENY_ALL = AccessDecision()
