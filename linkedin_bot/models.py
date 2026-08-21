"""
A simple box for one article we might write about.

title    = headline
link     = URL
summary  = short text the AI can quote from
reactions = likes / upvotes / points (0 if we do not know)
source   = where it came from, e.g. Reddit or Hacker News
"""
from dataclasses import dataclass


@dataclass
class CandidatePost:
    title: str
    link: str
    summary: str
    reactions: int
    source: str
