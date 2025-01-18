from sim_framework import *
from typing import Union


def add2sim_rent(
    sim: Sim,
    renter_account_name: str,
    owner_account_name: str,
    monthly_rent: Union[str, float],
    move_in_date: str,
    move_out_date: str,
):
    """Simulates rent payments from a renter to an owner, including prorated first month.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        renter_account_name (str): Account name of the renter paying rent (e.g., "Alice")
        owner_account_name (str): Account name of the owner receiving rent (e.g., "Atwood Apartments")
        monthly_rent (Union[str, float]): Monthly rent amount (e.g., 1000)
        move_in_date (str): Start date of rental period in MM/DD/YYYY format
        move_out_date (str): End date of rental period in MM/DD/YYYY format
    """
    owner_acc = sim.get_account(owner_account_name)
    renter_acc = sim.get_account(renter_account_name)

    # Convert string dates to Events
    move_in_event = Event(move_in_date)
    move_out_event = Event(move_out_date)

    # Calculate prorated rent for first partial month
    next_month = move_in_event.next_month()
    days_remaining = move_in_event.days_until(next_month)
    prorated_rent = sim.get_value(monthly_rent) * (
        days_remaining / move_in_event.days_in_month()
    )

    sim.add_actions(
        Action(
            name="first rent",
            action=lambda this: renter_acc.transfer_to(owner_acc, amt=prorated_rent),
            start=move_in_event.date,
            periodicity="once",
        ),
        Action(
            name="rent payment",
            action=lambda this: renter_acc.transfer_to(
                owner_acc, amt=sim.get_value(monthly_rent)
            ),
            periodicity="monthly",
            start=next_month,
            end=move_out_event.date,
        ),
    )


def add2sim_buy_house(
    sim: Sim,
    mortgage_account_name: str,
    lender_account_name: str,
    buyer_account_name: str,
    market_account_name: str,
    house_val_account_name: str,
    # ----------
    loan_rate: Union[str, float],
    appreciation_rate: Union[str, float],
    # ----------
    house_price: Union[str, float],
    downpayment: Union[str, float],
    buy_closing_cost: Union[str, float],
    mortgage: Union[str, float],
    # ----------
    buy_date: str,
    end_date: str,
):
    """Simulates buying, maintaining, and selling a house.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        mortgage_account_name (str): Account tracking mortgage debt (e.g., "mortgage")
        lender_account_name (str): The lender who profits from the interest payments (e.g., "bank")
        buyer_account_name (str): The buyer's account (e.g., "myself")
        market_account_name (str): Market forces (e.g., "housing_market")
        house_val_account_name (str): House asset (e.g., "mountain_view_house")
        loan_rate (Union[str, float]): Rate name in rates{} or a float value (e.g., "chase_loan_rate" or 0.05)
        appreciation_rate (Union[str, float]): Rate name in rates{} or a float value (e.g., "house_appreciation" or 0.03)
        house_price (Union[str, float]): Total house price (e.g., 300000)
        downpayment (Union[str, float]): Initial payment (e.g., 100000)
        buy_closing_cost (Union[str, float]): Purchase closing costs (e.g., 5000)
        mortgage (Union[str, float]): Total monthly payment for interest + principal(e.g., 2000)
        buy_date (str): Purchase date in MM/DD/YYYY format
        end_date (str): End date in MM/DD/YYYY format
    """
    buyer_acc = sim.get_account(buyer_account_name)
    house_val_acc = sim.get_account(house_val_account_name)
    mortgage_debt_acc = sim.get_account(mortgage_account_name)
    lender_acc = sim.get_account(lender_account_name)
    market_acc = sim.get_account(market_account_name)

    # Convert string dates to Events
    buy_event = Event(buy_date)
    end_event = Event(end_date)

    # Calculate initial interest for first partial month
    next_month = buy_event.next_month()
    days_until_next_month = buy_event.days_until(next_month)
    initial_interest = (
        abs(sim.get_value(house_price) - sim.get_value(downpayment))
        * sim.get_value(loan_rate)
        * days_until_next_month
        / 365
    )

    # Create interest transaction for reference in principal calculation
    interest_trx = Action(
        name="interest payment",
        action=lambda this: buyer_acc.transfer_to(
            lender_acc,
            amt=abs(mortgage_debt_acc.balance) * sim.get_value(loan_rate) / 12,
        ),
        # Only pay interest if debt is owed
        exec_condition=lambda: mortgage_debt_acc.balance < 0,
        periodicity="monthly",
        start=buy_event.next_month(skip_months=1),
        end=end_event.date,
    )

    sim.add_actions(
        # Initial transactions
        Action(
            name="borrow loan",
            action=lambda this: mortgage_debt_acc.transfer_to(
                buyer_acc, amt=sim.get_value(house_price) - sim.get_value(downpayment)
            ),
            start=buy_event.date,
        ),
        Action(
            name="buy house",
            action=lambda this: buyer_acc.transfer_to(
                house_val_acc, amt=sim.get_value(house_price)
            ),
            start=buy_event.date,
        ),
        Action(
            name="closing cost",
            action=lambda this: buyer_acc.transfer_to(
                lender_acc, amt=sim.get_value(buy_closing_cost)
            ),
            start=buy_event.date,
        ),
        Action(
            name="initial loan interest",
            action=lambda this: buyer_acc.transfer_to(lender_acc, amt=initial_interest),
            start=next_month,
            periodicity="once",
        ),
        # Monthly transactions
        interest_trx,
        Action(
            name="principal payoff",
            action=lambda this: buyer_acc.transfer_to(
                mortgage_debt_acc,
                amt=min(
                    max(
                        sim.get_value(mortgage) - interest_trx.last_amt,
                        0,
                    ),
                    -mortgage_debt_acc.balance,
                ),
            ),
            periodicity="monthly",
            start=buy_event.next_month(),
            end=end_event.date,
        ),
        Action(
            name="appreciation",
            action=lambda this: market_acc.transfer_to(
                house_val_acc,
                amt=house_val_acc.balance * sim.get_value(appreciation_rate) / 12,
            ),
            periodicity="monthly",
            start=buy_event.next_month(),
            end=end_event.date,
        ),
    )


def add2sim_sell_house(
    sim: Sim,
    seller_account_name: str,
    house_val_account_name: str,
    market_account_name: str,
    sell_closing_cost: Union[str, float],
    sell_date: str,
):
    """Simulates selling a house.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        seller_account_name (str): Account name of the seller (e.g., "myself")
        buyer_account_name (str): Account name of the buyer (e.g., "Alice")
        house_val_account_name (str): House asset account (e.g., "mountain_view_house")
        market_account_name (str): Market forces (e.g., "housing_market")
        sell_closing_cost (Union[str, float]): Selling closing costs (e.g., 5000)
        sell_date (str): Date of the sale in MM/DD/YYYY format
    """
    seller_acc = sim.get_account(seller_account_name)
    house_val_acc = sim.get_account(house_val_account_name)
    market_acc = sim.get_account(market_account_name)

    # Convert string date to Event
    sell_event = Event(sell_date)

    # Add actions for selling the house
    sim.add_actions(
        Action(
            name="sell house",
            action=lambda this: house_val_acc.transfer_to(
                seller_acc, amt=house_val_acc.balance
            ),
            start=sell_event.date,
        ),
        Action(
            name="pay closing cost",
            action=lambda this: seller_acc.transfer_to(
                market_acc, amt=sim.get_value(sell_closing_cost)
            ),
            start=sell_event.date,
        ),
    )


def add2sim_one_time_transaction(
    sim: Sim,
    src_account_name: str,
    dest_account_name: str,
    transaction_name: str,
    amount: Union[str, float],
    transaction_date: str,
):
    """Simulates a one-time transaction between two accounts.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        src_account_name (str): Account name incurring the cost (e.g., "Alice")
        dest_account_name (str): Account name receiving the cost (e.g., "Bob")
        transaction_name (str): Name of the transaction (e.g., "gift")
        amount (Union[str, float]): Amount of the transaction (e.g., 100)
        transaction_date (str): Date of the transaction in MM/DD/YYYY format
    """
    src_acc = sim.get_account(src_account_name)
    dest_acc = sim.get_account(dest_account_name)

    # Convert string date to Event
    transaction_event = Event(transaction_date)

    # Add one-time transaction action
    sim.add_actions(
        Action(
            name=transaction_name,
            action=lambda this: src_acc.transfer_to(
                dest_acc, amt=sim.get_value(amount)
            ),
            start=transaction_event.date,
            periodicity="once",
        )
    )


def add2sim_recurring_transaction(
    sim: Sim,
    src_account_name: str,
    dest_account_name: str,
    transaction_name: str,
    amount: Union[str, float],
    start_date: str,
    end_date: str,
    periodicity: str = "monthly",
):
    """Simulates recurring costs for an account.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        src_account_name (str): Account name incurring the cost (e.g., "Alice")
        dest_account_name (str): Account name receiving the cost (e.g., "utilities")
        transaction_name (str): Name of the cost (e.g., "utilities")
        amount (Union[str, float]): Amount of the recurring cost (e.g., 100)
        start_date (str): Start date of the recurring cost in MM/DD/YYYY format
        end_date (str): End date of the recurring cost in MM/DD/YYYY format
        periodicity (str): Frequency of the cost (e.g., "monthly", "weekly", "biweekly", "yearly"), default is "monthly"
    """
    src_acc = sim.get_account(src_account_name)
    dest_acc = sim.get_account(dest_account_name)

    # Convert string dates to Events
    start_event = Event(start_date)
    end_event = Event(end_date)

    # Add recurring cost action
    sim.add_actions(
        Action(
            name=transaction_name,
            action=lambda this: src_acc.transfer_to(
                dest_acc, amt=sim.get_value(amount)
            ),
            periodicity=periodicity,
            start=start_event.date,
            end=end_event.date,
        )
    )


def add2sim_get_loan(
    sim: Sim,
    borrower_account_name: str,
    lender_account_name: str,
    debt_account_name: str,
    loan_name: str,
    loan_amount: Union[str, float],
    loan_rate: Union[str, float],
    monthly_payment: Union[str, float],
    start_date: str,
    end_date: str,
):
    """Simulates getting a loan and making monthly interest payments.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        borrower_account_name (str): Account name of the borrower (e.g., "Alice")
        lender_account_name (str): Account name of the lender (e.g., "Bank")
        debt_account_name (str): Account name tracking the debt (e.g., "loan_debt")
        loan_name (str): Name of the loan (e.g., "Car Loan")
        loan_amount (Union[str, float]): Amount of the loan (e.g., 10000)
        loan_rate (Union[str, float]): Interest rate of the loan (e.g., 0.05)
        monthly_payment (Union[str, float]): Monthly payment amount (e.g., 200)
        start_date (str): Start date of the loan in MM/DD/YYYY format
        end_date (str): End date of the loan in MM/DD/YYYY format
    """
    borrower_acc = sim.get_account(borrower_account_name)
    lender_acc = sim.get_account(lender_account_name)
    debt_acc = sim.get_account(debt_account_name)

    # Convert string dates to Events
    start_event = Event(start_date)
    end_event = Event(end_date)

    # Calculate initial interest for first partial month
    next_month = start_event.next_month()
    days_until_next_month = start_event.days_until(next_month)
    initial_interest = (
        sim.get_value(loan_amount)
        * sim.get_value(loan_rate)
        * days_until_next_month
        / 365
    )

    # Create interest transaction for reference in principal calculation
    interest_trx = Action(
        name=f"{loan_name} interest payment",
        action=lambda this: borrower_acc.transfer_to(
            lender_acc,
            amt=abs(debt_acc.balance) * sim.get_value(loan_rate) / 12,
        ),
        # Only pay interest if debt is owed
        exec_condition=lambda: debt_acc.balance < 0,
        periodicity="monthly",
        start=start_event.next_month(skip_months=1),
        end=end_event.date,
    )

    sim.add_actions(
        # Initial loan disbursement
        Action(
            name=f"disburse {loan_name} loan",
            action=lambda this: debt_acc.transfer_to(
                borrower_acc, amt=sim.get_value(loan_amount)
            ),
            start=start_event.date,
        ),
        Action(
            name=f"initial {loan_name} interest",
            action=lambda this: borrower_acc.transfer_to(
                lender_acc, amt=initial_interest
            ),
            start=next_month,
            periodicity="once",
        ),
        # Monthly interest payments
        interest_trx,
        # Monthly principal payments
        Action(
            name=f"{loan_name} principal payment",
            action=lambda this: borrower_acc.transfer_to(
                debt_acc,
                amt=min(
                    max(
                        sim.get_value(monthly_payment) - interest_trx.last_amt,
                        0,
                    ),
                    -debt_acc.balance,
                ),
            ),
            periodicity="monthly",
            start=start_event.next_month(),
            end=end_event.date,
        ),
    )


def add2sim_modify_variable(
    sim: Sim,
    variable_name: str,
    new_value: Union[str, float],
    modification_date: str,
):
    """Simulates modifying a variable in the simulation on a specific date.

    Args:
        sim (Sim): The simulation object managing accounts and actions
        variable_name (str): Name of the variable to be modified (e.g., "interest_rate")
        new_value (Union[str, float]): New value to be set for the variable (e.g., "new_rate" or 0.05)
        modification_date (str): Date of the modification in MM/DD/YYYY format
    """
    # Convert string date to Event
    modification_event = Event(modification_date)

    # Add variable modification action
    sim.add_actions(
        Action(
            name=f"modify {variable_name}",
            action=lambda this: sim.vars.update(
                {variable_name: sim.get_value(new_value)}
            ),
            start=modification_event.date,
            periodicity="once",
        )
    )
