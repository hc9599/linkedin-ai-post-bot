from dataclasses import dataclass


@dataclass
class CandidatePost:
    title: str
    link: str
    summary: str
    reactions: int
    source: str
