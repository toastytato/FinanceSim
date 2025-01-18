import streamlit as st
import plotly.graph_objects as go
from langchain_google_genai import ChatGoogleGenerativeAI
import time
import json
import pandas as pd

from premade_actions import *
from sim_framework import *

IN_DEBUG = st.secrets.get("USE_DEBUG", False)
IS_LOCAL = st.secrets.get("IS_LOCAL", False)

if IS_LOCAL:
    import private

# Possible future change once you get the beta version out
# - make Accounts and variables the same thing: variables
# - Give them subtypes so that it can be specified
# - allow all variables the ability to be tracked
# - accounts are of the type balance
# - some could be of the type rates, costs, or other


def get_function_docs():
    functions = [
        add2sim_buy_house,
        add2sim_rent,
        add2sim_one_time_transaction,
        add2sim_recurring_transaction,
        add2sim_modify_variable,
    ]
    # Return formatted string of function names and their docstrings
    function_docs = ""
    for func in functions:
        function_docs += f"### {func.__name__}\n{func.__doc__}\n\n"
    return function_docs


container_height = 495

example_json = """
"scenarios": {              # List of scenarios to compare
    "scenario_name": {      # High-level scenario identifier (e.g., "Buy House", "Rent Apartment", "House + Roommate")
        "account_names": {    # Dictionary of accounts names and its starting balance which should be tracked over time
            "myself": 0,       # The main person in the scenario
            "mortgage": 0,     # Track mortgage debt balance
            "house": 0 ,        # Track house value
        },
        "variables": {            # Interest and appreciation rates used in calculations
            "loan_rate": 0.07,    # Example: 7% mortgage rate
            "house_appreciation": 0.05  # Example: 5% annual appreciation
            "rent_amt": 1500    # Example: a specified amount to be referenced later in the actions
        },
        "actions": [    # List of function calls with their parameters
            {
                "function": "add2sim_function",  # The name of the function to call
                "kwargs": {                      # Parameters specific to each function
                    "kwarg_name": "value"
                    ...
                }
            }
            ...
        ] 
    }
    ...
}
"""

example_json = """
{
"scenarios": {
    "HousePurchaseWithRefinance": {
        "account_names": {
            "myself": 0,
            "mortgage": 0,
            "house": 0,
            "family_debt": 0,
        },
        "variables": {
            "loan_rate_apr": 0.075,
            "fam_rate_apr": 0.04,
        },
        "actions": [
            {
                "function": "add2sim_buy_house",
                "kwargs": {
                    "mortgage_account_name": "mortgage",
                    "lender_account_name": "bank",
                    "buyer_account_name": "myself",
                    "market_account_name": "housing_market",
                    "house_val_account_name": "house",
                    "loan_rate": "loan_rate_apr",
                    "appreciation_rate": 0.08,
                    "house_price": 350e3,
                    "downpayment": 100e3,
                    "buy_closing_cost": 5000,
                    "mortgage": 1500,
                    "buy_date": "01/01/2024",
                    "end_date": "01/01/2030",
                },
            },
            {
                "function": "add2sim_modify_variable", // refinances the loan
                "kwargs": {
                    "variable_name": "loan_rate_apr",
                    "new_value": 0.06,
                    "modification_date": "01/01/2026",
                },
            },
            {
                "function": "add2sim_one_time_transaction", // cost of refinancing
                "kwargs": {
                    "src_account_name": "myself",
                    "dest_account_name": "bank",
                    "transaction_name": "Refinancing Cost",
                    "amount": 2000,
                    "transaction_date": "01/01/2026",
                },
            },
            {
                "function": "add2sim_sell_house",
                "kwargs": {
                    "seller_account_name": "myself",
                    "house_val_account_name": "house",
                    "market_account_name": "housing_market",
                    "sell_closing_cost": 6000,
                    "sell_date": "01/01/2030",
                },
            },
        ],
    },
    "Renting": {
        "account_names": {
            "myself": 0,
        },
        "variables": {},
        "actions": [
            {
                "function": "add2sim_recurring_transaction",
                "kwargs": {
                    "src_account_name": "myself",
                    "dest_account_name": "landlord",
                    "transaction_name": "Rent Payment",
                    "amount": 1300,
                    "start_date": "01/01/2024",
                    "end_date": "01/01/2030",
                    "periodicity": "monthly",
                },
            }
        ],
    },
},
}
"""

system_prompt = f"""
1. You are a financial adviser that uses the available tools to create simulation scenarios that matches the user's requests
2. Use the following add2sim functions and match its parameters as kwargs (IGNORE THE "sim:" PARAMETER IN THE FUNCTION DOCS):
{get_function_docs()}
3. This is an example JSON schema to follow:
```
{example_json}
```
4. Each scenario must be completely self-contained with ALL necessary actions
- If comparing "Buy House" vs "Buy House + Roommate", the second scenario must include both the house purchase AND the roommate actions
- Never rely on actions from other scenarios
- Any kwargs with a suffix of "_varname" MUST be a variable name that is defined in the variables section
- A start and end date MUST be provided for each scenario
- You are outputting in Markdown (but don't respond starting in ```), so all dollar signs be written like \$
- Use PascalCase for the variable names, but snake_case for the function calls
- DO NOT PUT COMMENTS IN THE JSON
5. After creating the JSON, summarize each of the scenarios you created
6. The account names should just track the user, their assets, and their liabilities. No one else
7. Variables should only be created if the user asks to modify some value halfway into the sim. Otherwise the add2sim premade functions will handle hardcoded values as indicated in the docs
8. If the function parameter allows for either str or float, the str value MUST BE INSTANTIATED IN THE "variables" DICTIONARY
9. If the variable is not being modified, no need to make it a variable. Just put a hardcoded value in the parameter instead
10. Do not shorten the final JSON. Every response should give the full JSON needed to simulate the user's request
11. You are just to help interface the user with the simulation engine, everything else is handled for you.\
12. Do not hallucinate kwargs for the add2sim functions
"""

initiate_welcome_prompt = """
Now that you have the instructions, a user has just joined. 
You are a helpful financial adviser who will answer their questions and setup the relevant scenarios when appropriate.
Welcome them in and explain what the user can do. Explain that you will generate a plot given the created scenario.
Give the user a small example prompt to start out with.
Keep this short"""


def parse_json(text: str) -> tuple[bool, dict]:
    """Extract content between triple backticks and parse as JSON.
    Returns (success, parsed_json)"""
    try:
        # Split by triple backticks and get the content
        parts = text.split("```")
        if len(parts) < 3:
            return False, {}

        # Get the content and clean it
        json_text = parts[1].replace("json", "").replace(" ", "")
        # Remove comments that start with //
        json_text = "\n".join(line.split("//")[0] for line in json_text.split("\n"))

        # Parse JSON and return it directly
        return True, json.loads(json_text)

    except Exception as e:
        print(e)
        return False, {}


def main():
    st.set_page_config(layout="wide")
    st.title("Financial Advisor")
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "sim_config" not in st.session_state:
        st.session_state.sim_config = None
    if "model" not in st.session_state:
        st.session_state.model = None

    user_input = st.chat_input("Let's chat!")

    left_col, right_col = st.columns(
        2, gap="small", border=True, vertical_alignment="bottom"
    )
    with st.sidebar:
        st.title("Settings")
        default = st.secrets.get("google_api_key", None) if IS_LOCAL else None
        google_api_key = st.text_input(
            "Google AI API Key", type="password", value=default
        )
        st.markdown(
            "Start by entering your Google API Key. To obtain one, visit [Google AI Studio](https://aistudio.google.com/apikey)."
        )

        if google_api_key:
            st.session_state.model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=google_api_key,
                temperature=0,
            )
            try:
                if not st.session_state.messages:
                    init_prompt = system_prompt + "\n" + initiate_welcome_prompt
                    response = st.session_state.model.invoke(init_prompt).content
                    st.session_state.messages.append(
                        {"role": "system", "content": init_prompt}
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
            except Exception as e:
                st.error("Model could not be initiated:" + str(e))
                st.stop()

            st.success("API Key updated successfully!")

    with left_col:
        st.title("Chat")
        # Create a container with fixed height for chat history
        chat_container = st.container(border=False)

        # Display chat history in scrollable container
        with chat_container:
            start_msg_idx = 0 if IN_DEBUG else 1
            for message in st.session_state.messages[start_msg_idx:]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # User input
        if user_input and st.session_state.model:
            # Add user message to chat history
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_input)
            st.session_state.messages.append({"role": "user", "content": user_input})

            # Invoke the model with the system message and user input
            response_streamer = st.session_state.model.stream(st.session_state.messages)
            # Stream assistant response
            response_text = ""
            with chat_container:
                with st.chat_message("assistant"):
                    response_container = st.empty()
                    for chunk in response_streamer:
                        for word in chunk.content.split(" "):
                            response_text += word + " "
                        response_container.markdown(response_text)
                        time.sleep(0.02)

            # Add assistant response to chat history
            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )

            # Check for JSON in response and store in session state
            is_valid, data = parse_json(response_text)
            if is_valid:
                st.session_state.sim_config = data
                st.session_state.sims = Sim.get_sims_from_config(
                    st.session_state.sim_config
                )
                for sim in st.session_state.sims:
                    sim.run()

    # Right column always shows the latest JSON data if available
    with right_col:
        plot_tab, config_data_tab = st.tabs(["Plot", "Config Data"])

        with plot_tab:
            st.subheader("Plot")
            try:
                # Sim Debug configs
                if IN_DEBUG and IS_LOCAL:
                    data = private.my_scenario
                    st.session_state.sim_config = data
                    st.session_state.sims = Sim.get_sims_from_config(data)

                    for sim in st.session_state.sims:
                        sim.run()
                if "sims" in st.session_state and st.session_state.sims is not None:
                    sim_options = [sim.name for sim in st.session_state.sims]
                    sel_sim_names = st.multiselect(
                        "Select scenarios to compare:",
                        options=sim_options,
                        default=sim_options,
                    )
                    desired_sims = [
                        sim
                        for sim in st.session_state.sims
                        if sim.name in sel_sim_names
                    ]

                    # get the unique give me accounts in all scenarios, and make it available for selection
                    all_columns = set()
                    for sim in desired_sims:
                        all_columns.update(sim.ledger.columns[5:])
                    selected_columns = st.multiselect(
                        "Select accounts to aggregate:",
                        options=list(all_columns),
                        default=list(all_columns),
                    )
                    if selected_columns:
                        fig = go.Figure(layout=dict(width=800, height=800))
                        for sim in desired_sims:
                            df = sim.ledger.copy()
                            df["total"] = df[
                                df.columns.intersection(selected_columns)
                            ].sum(axis=1)

                            def calculate_amt_mod(row, selected_columns):
                                if (
                                    row["from"] in selected_columns
                                    and row["to"] in selected_columns
                                ):
                                    # if the money is going "from" a tracked account "to" a tracked account, net difference is 0
                                    return 0
                                elif row["from"] in selected_columns:
                                    # if money is leaving "from" a tracked account, net difference is the -amt
                                    return -row["amt"]
                                else:
                                    # if money is going "to" a tracked account, net difference is the amt
                                    return row["amt"]

                            df["amt_mod"] = df.apply(
                                calculate_amt_mod,
                                axis=1,
                                selected_columns=selected_columns,
                            )
                            df["annotations"] = df["date"].map(
                                df.groupby("date").apply(
                                    lambda x: "<br>".join(
                                        f"<b>• {row['name']}: </b>${row['amt_mod']:,.2f}"
                                        for _, row in x.sort_values(
                                            by="amt_mod", ascending=False
                                        ).iterrows()
                                        if row["to"] in selected_columns
                                        or row["from"] in selected_columns
                                    )
                                    + f"<br><b><i> DELTA: </i></b>${x.loc[x['to'].isin(selected_columns) | x['from'].isin(selected_columns), 'amt_mod'].sum():,.2f}"
                                    + f"<br><b><i> NET TOTAL: </i></b>${x['total'].iloc[-1]:,.2f}"
                                )
                            )
                            fig.add_trace(
                                go.Scatter(
                                    x=df.date,
                                    y=df.total,
                                    mode="lines+markers",
                                    line=dict(dash="dot"),
                                    line_shape="hv",
                                    marker=dict(symbol="circle"),
                                    name=f"<b><u>{sim.name}</u></b>",  # Make the title bold and underlined
                                    hovertemplate="<br>%{customdata[0]}",
                                    customdata=df[["annotations"]].values,
                                    textfont=dict(size=50),  # Increase text size
                                )
                            )
                            first_day, first_day_total = list(
                                df[df["date"] == df["date"].min()].iloc[-1][
                                    ["date", "total"]
                                ]
                            )
                            last_day, last_day_total = list(
                                df[df["date"] == df["date"].max()].iloc[-1][
                                    ["date", "total"]
                                ]
                            )

                            fig.add_trace(
                                go.Scatter(
                                    x=[first_day, last_day],
                                    y=[first_day_total, last_day_total],
                                    mode="lines",
                                    line=dict(color="red", width=2, dash="dash"),
                                    name="Start to End Line",
                                    hoverinfo="skip",
                                )
                            )

                        fig.update_layout(
                            xaxis_title="Date",
                            yaxis_title="Net Total ($)",
                            title={
                                "text": "Timeline",
                                "x": 0.5,
                                "xanchor": "center",
                            },
                            hovermode="x unified",
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                            ),
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.write("No columns selected for plotting")
                else:
                    st.write("No plot data available")
            except Exception as e:
                st.error(f"Error displaying plot: {str(e)}")

        with config_data_tab:
            st.subheader("Config Data")
            if (
                "sim_config" in st.session_state
                and st.session_state.sim_config is not None
            ):
                st.json(st.session_state.sim_config, expanded=5)
            else:
                st.write("No JSON data available")

        # with df_output_tab:
        #     st.subheader("DF Output")
        #     if (
        #         "sims" in st.session_state
        #         and st.session_state.sims is not None
        #     ):
        #         for i, df in enumerate(st.session_state.sims):
        #             st.write(f"Simulation {i+1}")
        #             st.dataframe(df)
        #     else:
        #         st.write("No DataFrame data available")


if __name__ == "__main__":
    main()
