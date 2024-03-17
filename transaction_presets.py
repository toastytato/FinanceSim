import ledger as lg
from typing import Dict, List
from pprint import pprint
import matplotlib.pyplot as plt


def get_income(
    income_ledger: lg.Ledger,
    start,
    duration,
    salary,
    insurance_cost,
    tax_rate,
    ira_rate,
    **other_ledgers: Dict[str, lg.Ledger],
):
    """
    Calculate income and deductions for a given duration.

    Args:
        income_ledger (lg.Ledger): The ledger to record income transactions.
        start: The start date of the income transactions.
        duration: The duration you're working and getting paid.
        salary: The monthly salary amount.
        insurance_cost: The cost of insurance premiums.
        tax_rate: The tax rate applied to the income.
        ira_rate: The rate of income allocated to IRA deductions.
        **other_ledgers: Additional optional ledgers used in the function.

    Returns:
        List[lg.Transaction]: A list of income transactions and deductions.

    Other Optional Ledgers:
        - employer_ledger (lg.Ledger): The ledger for employer who will be paying you.
        - income_tax_ledger (lg.Ledger): The ledger for income tax who you will be paying to.
        - ira_ledger (lg.Ledger): The ledger for IRA deductions who you will be paying.
        - insurance_ledger (lg.Ledger): The ledger for insurance premiums who you will be paying.

    """
    get_paid = lg.Transaction(
        start=start,
        duration=duration,
        src=other_ledgers.get("employer_ledger"),
        dest=income_ledger,
        amt=lambda: salary / 12,
        note="income",
    )
    deductions = [
        lg.Transaction(
            start=start,
            duration=duration,
            src=income_ledger,
            dest=other_ledgers.get("income_tax_ledger"),
            amt=lambda: get_paid.get_amt * tax_rate,
            dep_transaction=get_paid,  # make sure this transaction is processed first
            note="income tax",
        ),
        lg.Transaction(
            start=start,
            duration=duration,
            src=income_ledger,
            dest=other_ledgers.get("ira_ledger"),
            amt=lambda: get_paid.get_amt * ira_rate,
            dep_transaction=get_paid,
            note="ira deductions",
        ),
        lg.Transaction(
            start=start,
            duration=duration,
            src=income_ledger,
            dest=other_ledgers.get("insurance_ledger"),
            amt=insurance_cost,
            note="insurance premiums",
        ),
    ]
    return [get_paid] + deductions


def get_tenant(
    cash_ledger: lg.Ledger,
    start,
    duration,
    rent,
    **other_ledgers,
):
    """
    Create a transaction for tenant rent.

    Args:
        cash_ledger (lg.Ledger): The cash ledger where the rent will be deposited.
        start: The start date of the rental period.
        duration: The duration of the rental period.
        rent: The amount of rent to be paid.
        **other_ledgers: Options include "tenant_ledger", the ledger representing the tenant paying the rent to you

    Returns:
        list: A list containing a single transaction object representing the tenant rent.

    """
    return [
        lg.Transaction(
            start=start,
            duration=duration,
            src=other_ledgers.get("tenant_ledger"),
            dest=cash_ledger,
            amt=rent,
            note="tenant rent",
        )
    ]


def get_house_purchase(
    house_ledger: lg.Ledger,
    cash_ledger: lg.Ledger,
    start,
    duration,
    house_price,
    hoa_fees,
    buy_closing_costs,
    annual_apprec_rate,
    #
    sell_closing_costs,
    **other_ledgers: Dict[str, lg.Ledger],
) -> List[lg.Transaction]:
    """
    Calculates the transactions involved in a house purchase.

    Args:
        house_ledger (lg.Ledger): The ledger representing the house.
        cash_ledger (lg.Ledger): The ledger representing cash.
        start: The start month of the house purchase.
        duration: The duration in months you stay in the house
        house_price: The price of the house.
        hoa_fees: The HOA fees.
        buy_closing_costs: The closing costs for buying the house.
        annual_apprec_rate: The annual appreciation rate of the house.
        sell_closing_costs: The closing costs for selling the house.
        **other_ledgers (Dict[str, lg.Ledger]): Additional ledgers.

    Returns:
        List[lg.Transaction]: A list of transactions involved in the house purchase.
    """

    # upfront costs
    buy_trans = lg.Transaction(
        start=start,
        duration=1,
        src=cash_ledger,
        dest=house_ledger,
        amt=lambda: house_price,
        note="house purchase",
    )

    buy_closing_trans = lg.Transaction(
        start=start,
        duration=1,
        src=cash_ledger,
        dest=other_ledgers.get("closing costs"),
        amt=buy_closing_costs,
        note="buy closing costs",
    )

    # ongoing costs
    hoa_trans = lg.Transaction(
        start=start + 1,
        duration=duration + 1,
        src=cash_ledger,
        dest=other_ledgers.get("hoa_ledger"),
        amt=hoa_fees,
        note="HOA",
    )
    tax_trans = lg.Transaction(
        start=start + 1,
        duration=duration + 1,
        src=cash_ledger,
        dest=other_ledgers.get("tax_ledger"),
        amt=(house_price * 0.0099) / 12,
        note="property tax",
    )

    # appreciation
    house_ledger.set_interest_rate(annual_apprec_rate)
    appreciation_trans = lg.Transaction(
        start=start + 1,
        duration=duration + 1,
        src=other_ledgers.get("appreciation"),
        dest=house_ledger,
        amt=lambda: house_ledger.prev_total * house_ledger.interest_rate,
        note="appreciation",
    )

    # getting rid of house cost
    sell_trans = lg.Transaction(
        start=start + duration,
        duration=1,
        src=house_ledger,
        dest=cash_ledger,
        amt=lambda: house_ledger.prev_total,
        note="house selling",
    )

    sell_close_trans = lg.Transaction(
        start=start + duration,
        duration=1,
        src=cash_ledger,
        dest=other_ledgers.get("agent_ledger"),
        amt=sell_closing_costs,
        note="selling costs",
    )
    return [
        buy_trans,
        buy_closing_trans,
        tax_trans,
        hoa_trans,
        sell_trans,
        sell_close_trans,
        appreciation_trans,
    ]


def refinance_house(
    cash_ledger: lg.Ledger,
    bank_ledger: lg.Ledger,
    start,
    cost,
    new_annual_rate,
    **other_ledgers: Dict[str, lg.Ledger],
):
    """
    Refinances a house by setting a new interest rate for the bank ledger and creating a transaction for the refinance cost.

    Parameters:
    - cash_ledger: The cash ledger from which the refinance cost will be deducted.
    - bank_ledger: The bank ledger that will have its interest rate updated.
    - start: The start month of the refinance transaction.
    - cost: The cost of the refinance.
    - new_annual_rate: The new annual interest rate for the bank ledger.
    - other_ledgers: Additional ledgers that may be involved in the refinance transaction.

    Returns:
    - A list containing a single transaction representing the refinance cost.

    """

    def refinance():
        """
        Updates the interest rate in the bank ledger and returns the cost of refinancing.
        Called when the refinance transaction is processed.

        Returns:
            cost (float): The cost of refinancing.
        """
        bank_ledger.set_interest_rate(new_annual_rate)
        return cost

    return [
        lg.Transaction(
            start=start,
            duration=1,
            src=cash_ledger,
            dest=other_ledgers.get("commissions"),
            amt=refinance,
            note="refinance cost",
        )
    ]


def get_loan(
    cash_ledger: lg.Ledger,
    bank_ledger: lg.Ledger,
    start,
    duration,
    loan_amt,
    payback_amt,
    annual_intr_rate,
    payback_grace_period=0,
    **other_ledgers,
) -> List[lg.Transaction]:
    """
    Calculates the transactions related to a loan.

    Args:
        cash_ledger (lg.Ledger): The ledger representing the cash account.
        bank_ledger (lg.Ledger): The ledger representing the bank account.
        start: The start date of the loan in month.
        duration: The duration of the loan in months.
        loan_amt: The amount of the loan.
        payback_amt: The amount to be paid back each month.
        annual_intr_rate: The annual interest rate for the loan.
        payback_grace_period: The grace period before the payback starts (default: 0).
        **other_ledgers: Additional ledgers that may be involved in the loan.

    Returns:
        List[lg.Transaction]: A list of transactions related to the loan.

    """
    take_loan = lg.Transaction(
        start=start,
        duration=1,
        src=bank_ledger,
        dest=cash_ledger,
        amt=lambda: loan_amt,
        note="loan",
    )

    bank_ledger.set_interest_rate(annual_intr_rate)
    interest = lg.Transaction(
        start=start + payback_grace_period + 1,
        duration=duration - payback_grace_period - 1,
        src=other_ledgers.get("interest_ledger"),
        dest=bank_ledger,
        amt=lambda: bank_ledger.prev_total * bank_ledger.interest_rate,
        note="interest",
    )

    pay_loan = lg.Transaction(
        start=start + payback_grace_period + 1,
        duration=duration - payback_grace_period - 1,
        src=cash_ledger,
        dest=bank_ledger,
        amt=payback_amt,
        note="mortgage",
    )
    return [take_loan, interest, pay_loan]


def get_rental_transactions(
    cash_ledger: lg.Ledger,
    start,
    duration,
    monthly_rent,
    security_deposit,
    **other_ledgers: Dict[str, lg.Ledger],
) -> List[lg.Transaction]:
    """
    Generate a list of rental transactions for a given rental period.

    Args:
        cash_ledger (lg.Ledger): The cash ledger from which the transactions will be made.
        start: The start date of the rental period in months.
        duration: The duration of the rental period in months.
        monthly_rent: The amount of monthly rent.
        security_deposit: The amount of the security deposit.
        **other_ledgers (Dict[str, lg.Ledger]): Additional ledgers to be used for the transactions.

    Returns:
        List[lg.Transaction]: A list of the rental transactions.
    """
    transactions = []

    # Security deposit
    deposit_transaction = lg.Transaction(
        start=start,
        duration=1,
        src=cash_ledger,
        dest=other_ledgers.get("rental_ledger"),
        amt=security_deposit,
        note="Security deposit",
    )
    transactions.append(deposit_transaction)

    # Monthly rent payments
    rent_transaction = lg.Transaction(
        start=start + 1,
        duration=duration,
        src=cash_ledger,
        dest=other_ledgers.get("landlord_ledger"),
        amt=monthly_rent,
        note="Monthly rent payment",
    )
    transactions.append(rent_transaction)

    # Security deposit refund
    refund_transaction = lg.Transaction(
        start=start + duration,
        duration=1,
        src=other_ledgers.get("rental_ledger"),
        dest=cash_ledger,
        amt=security_deposit,
        note="Security deposit refund",
    )
    transactions.append(refund_transaction)

    return transactions
