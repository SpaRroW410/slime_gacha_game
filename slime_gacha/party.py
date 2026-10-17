"""Party system. A party is a FIXED-size squad (size must be a multiple of 5). You may run many parties,
but a slime belongs to at most one. Only full parties can battle. Extend by adding formations/roles later.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .errors import InvalidAction


def validate_size(size: int) -> int:
    if not isinstance(size, int) or size <= 0 or size % 5 != 0:
        raise ValueError("Party size must be a positive multiple of 5 (5, 10, 15, ...).")
    return size


@dataclass
class Party:
    id: int
    name: str
    members: List[int] = field(default_factory=list)
    leader: Optional[int] = None         # slime id; None = the highest-level member leads
    temp: bool = False                   # formed by the Vice Keeper for a hunt: disbands when everyone is back

    def to_dict(self):
        return dict(id=self.id, name=self.name, members=list(self.members), leader=self.leader, temp=self.temp)


class PartyManager:
    def __init__(self, size: int = 5):
        self.size = validate_size(size)
        self.parties: Dict[int, Party] = {}
        self._next = 1

    # ---- queries ---------------------------------------------------------------
    def get(self, pid: int) -> Party:
        try:
            return self.parties[pid]
        except KeyError:
            raise InvalidAction(f"No party #{pid}.") from None

    def party_of(self, sid: int) -> Optional[Party]:
        return next((p for p in self.parties.values() if sid in p.members), None)

    def is_full(self, pid: int) -> bool:
        return len(self.get(pid).members) == self.size

    # ---- edits -------------------------------------------------------------------
    def create(self, name: str = "") -> Party:
        p = Party(self._next, name or f"Party {self._next}")
        self._next += 1
        self.parties[p.id] = p
        return p

    def add(self, pid: int, sid: int) -> None:
        p = self.get(pid)
        other = self.party_of(sid)
        if other:
            raise InvalidAction(f"Slime #{sid} is already in '{other.name}'.")
        if len(p.members) >= self.size:
            raise InvalidAction(f"'{p.name}' is full ({self.size}/{self.size}).")
        p.members.append(sid)

    def remove(self, sid: int) -> None:
        """Take a slime out of whatever party holds it (no error if none) - also used on death/merge."""
        for p in self.parties.values():
            if sid in p.members:
                p.members.remove(sid)

    def disband(self, pid: int) -> None:
        self.get(pid)
        del self.parties[pid]

    # ---- persistence ---------------------------------------------------------------
    def to_dict(self):
        return dict(size=self.size, next=self._next, parties=[p.to_dict() for p in self.parties.values()])

    def load(self, d: dict, valid_ids) -> None:
        self.parties = {}
        for pd in d.get("parties", []):
            members = [i for i in pd["members"] if i in valid_ids]
            leader = pd.get("leader")
            self.parties[pd["id"]] = Party(pd["id"], pd["name"], members, leader if leader in members else None,
                                           bool(pd.get("temp", False)))
        self._next = d.get("next", max(self.parties, default=0) + 1)
