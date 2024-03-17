from __future__ import annotations

import ledger as lg
import transaction_presets as tr
import visualization as vis
import matplotlib.pyplot as plt
from pprint import pprint
from copy import deepcopy
import typing


class Scenario:
    """
    Represents a hypothetical financial scenario that you'd like to project and compare.

    Attributes:
        name (str): The name of the scenario.
        all_transactions (list): A list of all transactions in the scenario.
        results (list): A list of ledgers that were used by the transactions.
        ledgers (dict): A dictionary of ledgers associated with the scenario.
                        Used to store ledgers that are passed into the transactions
    """

    def __init__(self, name="Scenario") -> None:
        self.name = name
        self.all_transactions = []
        self.results: list[lg.Ledger] = []
        self.ledgers: typing.Dict[str, lg.Ledger] = {}

    def create_ledgers(self, *names):
        """
        Create ledgers with the given names.

        Parameters:
        - names: Variable number of ledger names.
        """
        for n in names:
            self.ledgers[n] = lg.Ledger(n)

    def copy_scenario(self, s: Scenario):
        """
        Doesn't do anything right now
        Ideally you can pass in a scenario that you want to copy and then vary
        the parameters you care about.
        Requires that a deepcopy be made so that two scenarios are not writing
        to the same ledger and messing up the results
        """
        self.all_transactions += deepcopy(s.all_transactions)
        self.ledgers.update(deepcopy(s.ledgers))

    def add_transactions(self, transactions: list[lg.Transaction]):
        """
        Adds a list of transactions to the existing transactions.

        Parameters:
        transactions (list[lg.Transaction]): A list of transactions to be added.
        """
        self.all_transactions += transactions

    def simulate(self, duration):
        """
        Simulates the transactions for a given duration.

        Parameters:
        duration (int): The duration of the simulation in months.
        """
        self.all_ledgers = lg.simulate_transactions(self.all_transactions, duration)
        self.results = vis.aggregate_ledgers(
            [l.get_ledger() for l in self.all_ledgers],
            self.name,
        )
