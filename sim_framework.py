# %%
from typing import Self, Dict
import pandas as pd
import heapq as hq
from dateutil.relativedelta import relativedelta
import datetime
import numpy as np
import premade_actions

"""
Architecture:
- User specifies how to set up automated actions
- these actions can do any function
- will need to set up the data structures and giving them access
- make abstractions later for certain groups of actions 
"""


class Event:
    """
    A wrapper for datetime handling in financial simulations.
    Provides convenient methods for common financial date operations.
    """

    def __init__(self, date_str: str | pd.Timestamp) -> None:
        if isinstance(date_str, str):
            self.dt = pd.to_datetime(date_str, format="%m/%d/%Y")
        else:
            self.dt = date_str

    @property
    def date(self) -> pd.Timestamp:
        """Get the underlying timestamp"""
        return self.dt

    def next_month(self, skip_months: int = 0) -> pd.Timestamp:
        """Get the start of next month, optionally skip months"""
        return self.dt + relativedelta(months=1 + skip_months, day=1)

    def days_until(self, other_date: pd.Timestamp) -> int:
        """Get number of days between this event and another date"""
        return (other_date - self.dt).days

    def days_in_month(self) -> int:
        """Get the number of days in this event's month"""
        return (
            pd.Timestamp(self.dt.year, self.dt.month, 1)
            + relativedelta(months=1)
            - pd.Timestamp(self.dt.year, self.dt.month, 1)
        ).days

    def add_period(self, period: relativedelta) -> pd.Timestamp:
        """Add a time period to this event's date"""
        return self.dt + period

    @classmethod
    def from_timestamp(cls, timestamp: pd.Timestamp) -> "Event":
        """Create an Event from a pandas Timestamp"""
        return cls(timestamp)


class Account:
    def __init__(self, name, amt, type="") -> None:
        self.name = name
        self.balance = amt
        self.type = type

    @property
    def balance(self):
        return self._amt

    @balance.setter
    def balance(self, amt):
        self._amt = amt

    def deposit(self, delta):
        self.balance += delta
        return self.balance

    def withdraw(self, delta):
        self.balance -= delta
        return delta

    # paying someone and transferring money to them is the same thing
    def pay(self, other: Self, amt):
        self.transfer_to(other, amt)

    def transfer_to(self, other: Self, amt):
        withdrawn = self.withdraw(amt)
        other.deposit(withdrawn)
        receipt = {
            "from": self.name,
            "to": other.name,
            "amt": withdrawn,
        }
        return receipt

    def __lt__(self, other):
        return self.balance < other.amt

    def __gt__(self, other):
        return self.balance > other.amt

    def __eq__(self, other):
        return self.balance == other.amt

    def __repr__(self) -> str:
        return self.name


class Action:
    """
    Specifies the action to perform and when to perform said action
    """

    deltas = {
        "yearly": relativedelta(years=1),
        "monthly": relativedelta(months=1),
        "biweekly": relativedelta(weeks=2),
        "weekly": relativedelta(weeks=1),
        "daily": relativedelta(days=1),
    }

    def __init__(
        self,
        name: str,
        action: callable,
        start: pd.Timestamp,
        end: pd.Timestamp = None,
        periodicity: str = "once",
        exec_condition: callable = lambda: True,
    ) -> None:
        self.name = name

        self.action = action
        self.condition = exec_condition
        self.is_finished = False

        self.priority = 1
        self.start_date = start
        self.end_date = end if end is not None else datetime.datetime.max
        self.execute_date = self.start_date
        self.periodicity = periodicity if periodicity else "once"
        self.period = self.deltas.get(self.periodicity, None)
        self.last_amt = 0

    def yearly_frequency(self):
        # returns the number of Action occurrences per year
        if self.periodicity == "monthly":
            return 12 / self.period.months
        elif self.periodicity in ["biweekly", "weekly"]:
            return (365 / 7) / self.period.weeks
        else:  # "once"
            return 1

    def execute(self):
        valid = False
        if self.condition() and self.execute_date < self.end_date:
            receipt = self.action(self)  # pass in self as a parameter
            valid = True
            if receipt is None:
                receipt = {}
            # receipts from Account transfers will contain {"to", "from", "amt"}
            receipt["date"] = self.execute_date
            receipt["name"] = self.name
            self.last_amt = receipt.get("amt", 0)

            if self.period:
                self.execute_date += self.period
                if self.execute_date >= self.end_date:
                    self.is_finished = True
            else:
                self.is_finished = True
        else:
            self.is_finished = True
            receipt = {}

        return valid, receipt

    def stop(self):
        self.end_date = self.execute_date

    def __lt__(self, other: Self):
        if self.execute_date == other.execute_date:
            return self.priority < other.priority
        else:
            return self.execute_date < other.execute_date

    def __gt__(self, other: Self):
        if self.execute_date == other.execute_date:
            return self.priority > other.priority
        else:
            return self.execute_date > other.execute_date

    # def __eq__(self, other: Self):
    #     return (
    #         self.execute_date == other.execute_date and self.priority == other.priority
    #     )

    def __repr__(self):
        return self.name


class Sim:
    """
    Store the state variables in an object so that it can be changed and still be referenced
    by the actions during simulation
    """

    def __init__(self, name="") -> None:
        # all could get modified by the run
        self.name = name
        self.accounts: Dict[str, Account] = {}
        self.vars = {}
        self.actions = []
        self.ledger = pd.DataFrame(
            columns=["date", "name", "from", "to", "amt"]
            + [acc.name for acc in self.accounts.values()]
        )

    def get_value(self, value):
        # parses the input value which can either be a hardcoded value or a variable
        return self.vars[value] if isinstance(value, str) else value

    @classmethod
    def get_sim_from_scenario(cls, scenario_name: str, scenario_data: Dict):
        sim = cls(scenario_name)
        for account_name, starting_amt in scenario_data["account_names"].items():
            sim.create_account(account_name, amt=starting_amt)

        for var_name, var_value in scenario_data["variables"].items():
            sim.vars[var_name] = var_value

        for action in scenario_data["actions"]:
            function_name = action["function"]
            kwargs = action["kwargs"]
            add2sim_func = getattr(premade_actions, function_name)
            add2sim_func(sim, **kwargs)

        return sim

    @classmethod
    def get_sims_from_config(cls, config: Dict):
        sims = []
        for scenario_name, scenario_data in config["scenarios"].items():
            sim = cls.get_sim_from_scenario(scenario_name, scenario_data)
            sims.append(sim)
        return sims

    def create_account(self, name, amt=0):
        self.accounts[name] = Account(name, amt=amt)

    def get_account(self, name: str) -> Account:
        """Get an account by ID, returning a placeholder if it doesn't exist."""
        if name not in self.accounts.keys():
            # Create a placeholder account that will be used for simulation
            # but won't affect the actual results
            return Account(name, 0)
        return self.accounts[name]

    def add_action(self, action: Action):
        # adds a single transcation
        self.actions.append(action)

    def add_actions(self, *args: Action):
        # accepts multiple transactions
        all_actions = list(args)  # convert from tuple to list
        self.actions += all_actions  # concatenate lists

    def clean_order(self, actions: list[Action]):
        # assign priorities based on the order in which the actions were added to the list
        # higher priorities will get evaluated first if both actions are to be executed at the same time
        actions_sorted = sorted(actions)
        for i in range(1, len(actions_sorted)):
            if actions_sorted[i].start_date == actions_sorted[i - 1].start_date:
                actions_sorted[i].priority = actions_sorted[i - 1].priority + 1
        return actions_sorted

    def run(self, num_iters=np.inf):
        print("---INIT---")
        for acc in self.accounts.values():
            self.ledger.loc[0, acc.name] = acc.balance

        self.actions = self.clean_order(self.actions)
        print(self.actions)
        iters = 0

        while len(self.actions) and (iters < num_iters):
            action: Action = hq.heappop(self.actions)  # get the earliest action
            # print(f"{t.name}")
            i = len(self.ledger.index)
            valid, receipt = action.execute()  # action gets executed and updated

            if valid:
                self.ledger.loc[i] = receipt
                for acc in self.accounts.values():
                    self.ledger.loc[i, acc.name] = acc.balance

            if not action.is_finished:
                hq.heappush(self.actions, action)

            iters += 1

        self.ledger.loc[0, ["date", "amt"]] = self.ledger.loc[1, ["date", "amt"]]
