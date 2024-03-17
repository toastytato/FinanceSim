import matplotlib.pyplot as plt
from matplotlib import cm
import pandas as pd
from ledger import Ledger
import mplcursors
import matplotlib.ticker as ticker


def aggregate_ledgers(ledger_dfs, name=None):
    """
    Aggregate multiple ledgers into a single DataFrame.

    Parameters:
    - ledger_dfs (list): A list of pandas DataFrames representing individual ledgers.
    - name (str, optional): The name to assign to the aggregated ledger. If not provided, the names of the individual ledgers will be concatenated with '+'.

    Returns:
    - df (pandas DataFrame): The aggregated ledger DataFrame with the top column as the name
                            and the second columns for total, delta, and notes .
        The new df is indexed soley by month
        The deltas in for each month across all ledgers are summed
        The total is the cumulative sum of all deltas
        The notes are merged into a single string
    """

    # TODO: Take in Ledger objects instead of df to have a known dataframe format

    # Combine ledgers into a single DataFrame
    if not name:
        name = "+".join([l.columns.unique("name")[0] for l in ledger_dfs])

    df = pd.DataFrame(
        {},
        columns=pd.MultiIndex.from_product(
            [[name], ["total", "delta", "notes"]], names=["name", ""]
        ),
    )

    if not ledger_dfs:
        return

    combined_ledger = pd.concat(ledger_dfs, axis=1)
    # aggregate cross each ledger
    all_deltas = combined_ledger.xs("delta", level=1, axis=1).fillna(0).sum(axis=1)
    all_notes = (
        combined_ledger.xs("notes", level=1, axis=1)
        .fillna(False)
        .apply(lambda x: ", ".join(set([s for s in x if s])), axis=1)
    )
    # aggregate across each month
    df[(name, "delta")] = all_deltas.groupby("month").sum()
    df[(name, "total")] = df[(name, "delta")].cumsum()
    df[(name, "notes")] = all_notes.groupby("month").agg(
        lambda x: ",".join(set([s for s in x if s]))
    )

    return df


def visualize_df(*ledger_dfs):
    """
    Plots each dataframe against each other in delta/total vs months

    Parameters:
    - ledger_dfs: Variable number of ledger dataframes to be visualized.
    """

    # Create the plot
    fig, (total_ax, delta_ax) = plt.subplots(2)

    for i, df in enumerate(ledger_dfs):
        if df is None:
            continue
        df = df.reset_index(col_level=1)
        df_name = "".join(df.columns.unique(level="name"))

        delta_ax.set_xlabel("Months")
        delta_ax.set_ylabel("$ Delta")
        delta_ax.step(
            df.xs("month", level=1, axis=1),
            df.xs("delta", level=1, axis=1),
            label=df_name,
            where="post",
        )
        delta_ax.legend()

        total_ax.set_xlabel("Months")
        total_ax.set_ylabel("$ Total")
        total_ax.step(
            df.xs("month", level=1, axis=1),
            df.xs("total", level=1, axis=1),
            label=df_name,
            where="post",
        )
        total_ax.legend()

    delta_ax.set_title("Deltas")
    total_ax.set_title("Totals")
    delta_ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    total_ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    fig.suptitle("Finances")
    fig.tight_layout()
    plt.show()
