from scenarios import Scenario
import ledger as lg
import transaction_presets as tr
import visualization as vis
from pprint import pprint

if __name__ == "__main__":

    # ---- Homeowner Scenario Setup ------------
    move_in = 3  # in months since start (sim starts at month 1)
    stay_duration = 20  # in months
    homeowner = Scenario("Owning")
    homeowner.create_ledgers(  # create ledgers to keep track of states
        "cash",
        "home_loan",
        "fam_loan",
        "house_val",
    )
    # Include transactions of interest
    # able to just delete or add in transactions pertaining to your scenario
    # you can also add in more presets. See transaction_presets.py for the format
    homeowner.add_transactions(
        tr.get_loan(  # home loan
            cash_ledger=homeowner.ledgers["cash"],
            bank_ledger=homeowner.ledgers["home_loan"],
            start=move_in,
            duration=stay_duration,
            loan_amt=100e3,
            payback_amt=2e3,  # mortgage
            annual_intr_rate=7,  # APR: yearly rate charged in %
        )
        + tr.get_loan(  # dad loan
            cash_ledger=homeowner.ledgers["cash"],
            bank_ledger=homeowner.ledgers["fam_loan"],
            start=move_in,
            duration=stay_duration,
            loan_amt=10e3,  # how much did you borrow
            payback_amt=100,  # how much are you paying each month
            payback_grace_period=4,  # how long until you have to start paying back
            annual_intr_rate=3,  # units of %
        )
        + tr.get_house_purchase(
            house_ledger=homeowner.ledgers["house_val"],
            cash_ledger=homeowner.ledgers["cash"],
            start=move_in,
            duration=stay_duration,
            house_price=200e3,
            hoa_fees=100,
            buy_closing_costs=10e3,
            sell_closing_costs=10e3,
            annual_apprec_rate=5,  # units of %
        )
        + tr.refinance_house(
            cash_ledger=homeowner.ledgers["cash"],
            bank_ledger=homeowner.ledgers["home_loan"],
            start=10,
            cost=1e3,
            new_annual_rate=3,
        )
        + tr.get_tenant(
            cash_ledger=homeowner.ledgers["cash"],
            start=move_in + 5,
            duration=stay_duration - 5,
            rent=1e3,
        )
    )

    # ----- Rental Scenario-------
    renter = Scenario("Renting")
    renter.create_ledgers("cash")
    renter.add_transactions(
        tr.get_rental_transactions(
            cash_ledger=renter.ledgers["cash"],
            start=move_in,
            duration=stay_duration,
            monthly_rent=1800,
            security_deposit=900,
        )
    )

    # ---- View transactions that will be processed ----
    pprint(homeowner.all_transactions)
    pprint(renter.all_transactions)

    # --- Simulate ---
    sim_months = 30
    homeowner.simulate(sim_months)
    renter.simulate(sim_months)

    # --- View results in tabular format ---
    pprint(homeowner.ledgers["cash"].ledger)
    pprint(homeowner.results)

    # --- View results in graphical format ---
    vis.visualize_df(homeowner.results, renter.results)
