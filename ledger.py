"""
Any time there's a conflict 
- a transaction to/from the same ledger in the same month

Increment the subindex
"""

from __future__ import annotations

import pandas as pd
from typing import Callable


class Ledger:
    instances = 0

    def __init__(self, name="Ledger", init_delta=0) -> None:
        Ledger.instances += 1
        # self.name = f"{Ledger.instances}_{name}"
        self.name = name
        self.idx = 0
        self.month = 0
        self.interest_rate = 0  # monthly interest rate

        self.ledger = pd.DataFrame(
            {
                "month": self.month,
                "total": 0,
                "delta": 0,
                "interest_rate": 0,
                "notes": "",
            },
            index=[self.idx],
        )
        self.deposit(init_delta, "init")

    def get_ledger(self):
        return (
            pd.concat(
                {
                    self.name: self.ledger.reset_index()
                    .set_index(["month", "index"])
                    .transpose()
                },
                names=["name"],
            )
            # .swaplevel()
            .transpose()
        )
        # df = self.ledger.reset_index().set_index(["month", "index"])
        # df.name = self.name
        # return df

    def increment_month(self):
        self.month += 1
        # self.idx=0

    def set_interest_rate(self, annual_percentage_rate):
        self.interest_rate = (annual_percentage_rate / 100) / 12
        # self.ledger.loc[self.idx, "interest_rate"] = self.interest_rate

    @property
    def prev_idx(self):
        if self.idx != self.ledger.index[-1]:
            return max(self.idx - 1, 0)
        else:
            if len(self.ledger.index) > 1:
                return self.ledger.index[-2]
            else:
                return self.ledger.index[-1]

    @property
    def prev_total(self):
        return self.ledger.loc[self.prev_idx, "total"]

    @property
    def prev_delta(self):
        if self.ledger.loc[self.prev_idx, "month"] >= self.month - 1:
            return self.ledger.loc[self.prev_idx, "delta"]
        else:
            return 0

    def deposit(self, amt, notes=""):
        self.ledger.loc[self.idx, "month"] = self.month
        self.ledger.loc[self.idx, "total"] = self.prev_total + amt
        self.ledger.loc[self.idx, "delta"] = amt
        self.ledger.loc[self.idx, "notes"] = notes
        self.idx += 1

    def withdraw(self, amt, notes=""):
        self.ledger.loc[self.idx, "month"] = self.month
        self.ledger.loc[self.idx, "total"] = self.prev_total - amt
        self.ledger.loc[self.idx, "delta"] = -amt
        self.ledger.loc[self.idx, "notes"] = notes
        self.idx += 1

    def __repr__(self) -> str:
        return f"{self.name}"


class Transaction:
    def __init__(
        self,
        start: int,
        duration: int,
        src: Ledger,
        dest: Ledger,
        amt: int | float | Callable,
        amt_in: list = None,
        period: int = 1,
        dep_transaction: Transaction = None,
        note: str = "",
        priority: int = 1,
    ) -> None:
        self.start = start
        if dep_transaction:
            self.priority = dep_transaction.priority + 1
            self.end = dep_transaction.end
        else:
            self.priority = priority
            self.end = start + duration

        self.period = period
        self.src = src
        self.dest = dest
        self._amt = amt
        self.note = note
        self.month = 0

    def get_amt(self):
        # make sure not to call the function before desired time
        # it can update state variables in other objects
        if isinstance(self._amt, Callable):
            amt = self._amt()
        else:
            amt = self._amt
        return amt

    def set_amt(self, value: int | float | Callable):
        self._amt = value

    def process(self, month):
        self.month = month
        if self.start <= month < self.end and (self.start - month) % self.period == 0:
            amt = self.get_amt()

            if not amt:
                return

            # self.src.m = month
            # self.dest.m = month

            # this way the entry show up in the same index
            # makes it easy to see where the money flowed
            if self.src and self.dest:
                idx = max(self.src.idx, self.dest.idx)
                self.src.idx = idx
                self.dest.idx = idx

            if self.src:
                self.src.withdraw(amt, self.note)
            if self.dest:
                self.dest.deposit(amt, self.note)

    def __repr__(self) -> str:
        return f"{self.note}: {self.src} --> {self.dest} starting at ${self._amt} from months {self.start} to {self.end}, priority={self.priority}"


class Group:
    def __init__(self, ledgers: list[Ledger]) -> None:
        self.ledgers = ledgers

    def increment_month(self):
        for ledger in self.ledgers:
            ledger.increment_month()

    def add_account(self, account):
        self.ledgers.append(account)
        return account

    def merge_ledger(self):
        self.ledger = pd.concat(
            [a.get_ledger() for a in self.ledgers], axis=1
        ).sort_index(level=0)
        # self.ledger = self.ledger.fillna(0)

    def totals(self):
        return self.ledger.loc[:, "total"]

    def deltas(self, group=True):
        ledger = self.ledger.loc[:, "delta"]
        return ledger


def simulate_transactions(
    transactions: list[Transaction],
    duration: int,
):
    src_ledgers = [t.src for t in transactions if t.src is not None]
    dest_ledgers = [t.dest for t in transactions if t.dest is not None]
    ledgers = list(set(src_ledgers + dest_ledgers))
    for m in range(duration):
        [t.process(m) for t in transactions]
        [l.increment_month() for l in ledgers]
    return ledgers
