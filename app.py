import streamlit as st
import plotly.graph_objects as go
from langchain_google_genai import ChatGoogleGenerativeAI
import time
import json
import pandas as pd

from premade_actions import *
from sim_framework import *

st.set_page_config(page_title="FinSim", layout="wide")

USE_DEBUG = st.secrets.get("USE_DEBUG", False)
IS_LOCAL = st.secrets.get("IS_LOCAL", False)
SHARE_API = st.secrets.get("SHARE_API", False)

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
        add2sim_sell_house,
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
"scenarios": {  // list of scenarios to compare. 
    "HousePurchaseWithRefinance": { // relevant name for the scenario at hand
        "account_names": { // only track accounts relevant to net worth of the user (cash, assets and liabilities)
            "myself": 0, // cash of the user (initial value)
            "mortgage": 0, // liability of the user (initial value)
            "house": 0, // asset of the user (initial value)
            "family_debt": 0, // liability of the user (initial value)
        },
        "variables": { // only created if there will be an action changing the value during the sim
            "loan_rate_apr": 0.075,
            "fam_rate_apr": 0.04,
        },
        "actions": [
            {
                "function": "add2sim_buy_house", // uses the available add2sim functions
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
                    "variable_name": "loan_rate_apr", // references a variable from the "variables" field
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
    "Renting": { // note how a new scenario was screated for this separate comparison case
        "account_names": { // only tracks "myself" since no asset or liabilities to manage
            "myself": 0,
        },
        "variables": {}, // no variables to track in this scenario because nothing changes in midway in the sim
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
You are a financial adviser with access to simulation tools to fulfill the user's requests
Use the following add2sim functions and match its parameters as kwargs (IGNORE THE "sim:" PARAMETER IN THE FUNCTION DOCS): {get_function_docs()}
Do not hallcuinate or make up functions nor kwargs
This is an example JSON schema to follow: ```{example_json}```
You will respond to the user to answer their questions, and if the context makes sense create a JSON code block to create the simulation setup
Assume the system you're in will replace the JSON with the simulation output, so do not refer to the JSON. Simply refer to it as the simulation output
You are outputting in markdown, so all dollar signs should be written like \$
The account names must only track accounts relevant to the user's net worth
When you make a change, do NOT refer back to the specific configuration implementation you have generated
Every scenario in the list of scenarios must be fully self contained. Do not combine different scenarios into one
"""

# other = """
# 4. Each scenario must be completely self-contained with ALL necessary actions
# - Never rely on actions from other scenarios
# - Any kwargs with a suffix of "_varname" MUST be a variable name that is defined in the variables section
# - A start and end date MUST be provided for each scenario
# - You are outputting in Markdown (but don't respond starting in ```), so all dollar signs be written like \$
# - Use PascalCase for the variable names, but snake_case for the function calls
# 5. After creating the JSON, summarize each of the scenarios you created
# 6. **The account names should just track values associated with the current user's net worth (the user, their assets and debts/liabilities), nobody else**.
# 7. Variables should only be created if the user asks to modify some value halfway into the sim. Otherwise the add2sim premade functions will handle hardcoded values as indicated in the docs
# 8. If the function parameter allows for either str or float, the str value MUST BE INSTANTIATED IN THE "variables" DICTIONARY
# 9. If the variable is not being modified, no need to make it a variable. Just put a hardcoded value in the parameter instead
# 10. Do not shorten the final JSON. Every response should give the full JSON needed to simulate the user's request
# 11. You are just to help interface the user with the simulation engine, everything else is handled for you.
# 12. Do not hallucinate kwargs for the add2sim functions
# 13. If the user request cannot be accomplished with the given functions, let them know and do not generate the scenarios
# 14. If you are making a comparison, each one will need its own scenario
# """

initiate_welcome_prompt = """
Now that you have the instructions, a user has just joined. 
You are a helpful financial adviser who will answer their questions and setup the relevant scenarios when appropriate.
1. Welcome them in and explain what the user can do (give a variety of example prompts, some which are comparisons). 
2. Select one of the prompts you gave and then create the simulation setup following the schema shown previously. Say you are generating the simulation setup
3. Summarize the values you chose and tie it back to the context of the request. Use bullet points
4. Ask the user to try modifying the config in general terms, make up a scenario for them, or just ask you general finance questions.
Keep this short"""


howto_guide = """
Dang, personal finance terms can be so confusing sometimes. Worry not, this flexible tool lets AI translate your anticipated financial decisions to be run through a simulation.
You can ask it to:

 - simulate buying a house
 - compare different interest rates and upfront costs
 - refinance the house few years in
 - compare buying vs renting
 - model recurring expenses you have
 - (eventually) opportunity costs of different investments

You can see how your net worth (cash + assets + liabilities) will evolve over time in the plot.
Just chat with it to get personalized advice!
"""
# howto_guide = """
# Unlock the power of advanced financial simulations with our AI-driven tool.
# Whether you're buying a house, renting, refinancing loans, or planning any financial decision, our tool models complex scenarios and projects future outcomes.
# Simply describe your situation, and it generates detailed simulations and interactive plots, helping you make informed decisions with confidence.
# Perfect for anyone looking to visualize and optimize their financial future."""


def parse_response(response):
    precode_text = ""
    code_text = ""
    postcode_text = ""
    if "```" not in response:
        precode_text = response
    else:
        # split the start of the code block
        split = response.split("```json")
        precode_text = split[0]
        # split the end of the code block
        code_text = split[1].split("```")[0]
        postcode_text = split[1].split("```")[1]

    # Remove comments that start with //
    code_text = "\n".join([line.split("//")[0] for line in code_text.split("\n")])

    return precode_text, code_text, postcode_text


def main():
    st.title("Financial Advisor")
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "sim_config" not in st.session_state:
        st.session_state.sim_config = None
    if "model" not in st.session_state:
        st.session_state.model = None

    chat_input = st.chat_input("Let's chat!")
    is_system = False

    # Remove the two-column layout and just use a single column
    with st.sidebar:
        st.title("How-to Guide")
        st.markdown(howto_guide)

        st.title("Settings")
        if SHARE_API:
            default = "don't worry bout it i gotchu"
            st.text_input("Google AI API Key", value=default)
            google_api_key = st.secrets.get("google_api_key", None)
        else:
            default = st.secrets.get("google_api_key", None) if IS_LOCAL else None
            google_api_key = st.text_input(
                "Google AI API Key", type="password", value=default
            )
        st.markdown(
            "Start by entering your Google API Key. To obtain one, visit [Google AI Studio](https://aistudio.google.com/apikey)."
        )

        if google_api_key and not st.session_state.model:
            st.session_state.model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=google_api_key,
                temperature=0,
            )
            chat_input = system_prompt + "\n" + initiate_welcome_prompt
            is_system = True

            try:
                response = st.session_state.model.invoke("hi").content
            except Exception as e:
                st.error("Model could not be initiated:" + str(e))
                st.stop()

            st.success("API Key updated successfully!")

    # Replace the left_col with a single container
    left_col, right_col = st.columns(2, vertical_alignment="bottom")
    with left_col:
        chat_container = st.container(border=True)
    with right_col:
        test_container = st.container(border=True, height=730)

    with chat_container:
        st.title("Chat")
        # Display chat history
        display_chat_history(chat_input)

        # only executed when there is a new entry from the user
        # displays the response in realtime from the LLM API
        if chat_input and st.session_state.model:
            # don't show system prompt when in production
            if not is_system or USE_DEBUG:
                with st.chat_message("user"):
                    st.text(chat_input)
            st.session_state.messages.append({"role": "user", "content": chat_input})

            # Invoke the model with the system message and user input
            llm_streamer = st.session_state.model.stream(st.session_state.messages)

            with st.chat_message("assistant"):
                full_response = display_llm_stream(llm_streamer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
                # Add responses to chat history
                pre, code, post = parse_response(full_response)
                # the response contains setup code for the simulation
                # pre is displayed during the display_llm_stream

                if code:
                    try:
                        data = json.loads(code)
                    except Exception as e:
                        # bad code was generated
                        st.error(e)
                        st.code(code)
                        data = None
                else:
                    # just a normal response without code
                    data = None

                if data:
                    with st.spinner("Running sims..."):
                        st.session_state.sim_config = data

                    with st.spinner("Plotting results..."):
                        # plot_sim_data(1)
                        with st.popover("See the Generated Config"):
                            st.json(st.session_state.sim_config)

                if post:
                    post_code_text = ""
                    post_container = st.empty()
                    for word in post.split(" "):
                        post_code_text += word + " "
                        post_container.markdown(post_code_text)
                        time.sleep(0.01)

    with test_container:
        config_tab, plot_tab = st.tabs(["Configs", "Plot"])
        with config_tab:
            config_input = st.text_area(
                "Configs",
                value=json.dumps(st.session_state.sim_config, indent=2),
                height=550,
            )
            st.session_state.sim_config = json.loads(config_input)

            rerun = st.button("Update Plot")
            if rerun:
                with st.spinner("Running sims..."):
                    run_sims()
        with plot_tab:
            plot_sim_data(3)


def run_sims():
    st.session_state.sims = Sim.get_sims_from_config(st.session_state.sim_config)
    sim = st.session_state.sims
    for sim in st.session_state.sims:
        sim.run()


def display_chat_history(chat_input):
    start_msg_idx = 0 if USE_DEBUG else 1
    if USE_DEBUG:
        all_msgs = st.session_state.messages
    else:
        all_msgs = st.session_state.messages[1:][-6:]
    for message in all_msgs:
        is_latest = message == st.session_state.messages[-1]
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.text(message["content"])
            elif message["role"] == "assistant":
                # if we are updating that chat NOT from a user input
                pre, code, post = parse_response(message["content"])
                st.markdown(pre)
                if code:
                    if is_latest and not chat_input:
                        # occurs when the screen gets refreshsed
                        # and we're redrawing last output NOT triggered by user input
                        # plot_sim_data(2)
                        pass
                    else:
                        with st.popover("See Generated Code"):
                            st.json(code)
                    st.markdown(post)


def display_llm_stream(llm_streamer):
    # parses what the LLM is saying in real-time
    # stops streaming when code block is reached

    pre_code_response_container = st.empty()

    in_code_block = False

    # Stream assistant response
    full_response_text = ""
    pre_code_response = ""

    while not in_code_block:
        chunk = next(llm_streamer, None)
        if not chunk:
            break
        full_response_text += chunk.content

        # parse word by word
        for word in chunk.content.split(" "):
            if "```" in word:
                # sometimes the LLM combines other words with the delimiter
                in_code_block = True
                if in_code_block:
                    pre_code_response += word.split("```")[0]
                break
            else:
                pre_code_response += word + " "

        if USE_DEBUG:
            pre_code_response_container.text(full_response_text)
        else:
            pre_code_response_container.markdown(pre_code_response)

        time.sleep(0.02)

    # get the remaining response from the stream after parsing the code part
    with st.spinner("Parsing setup..."):
        for chunk in llm_streamer:
            full_response_text += chunk.content
            if USE_DEBUG:
                pre_code_response_container.text(full_response_text)

    return full_response_text


def plot_sim_data(key):
    # Plot simulation data using Plotly
    # The 'key' parameter is used to uniquely identify the plot in Streamlit.
    # This ensures that the plot updates correctly when the data changes.

    if "sims" in st.session_state and st.session_state.sims:
        desired_sims = st.session_state.sims

        all_columns = set()
        for sim in desired_sims:
            all_columns.update(sim.ledger.columns[5:])
        selected_columns = st.multiselect(
            "Select accounts to aggregate:",
            options=list(all_columns),
            default=list(all_columns),
            key=f"multisel{key}",
        )

        if selected_columns:
            try:
                fig = go.Figure(layout=dict(height=600))
                for sim in desired_sims:
                    df = sim.ledger.copy()
                    df["total"] = df[df.columns.intersection(selected_columns)].sum(
                        axis=1
                    )

                    def calculate_amt_mod(row, selected_columns):
                        # calculate modified amount based on who the money is going to
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
                        df[df["date"] == df["date"].min()].iloc[-1][["date", "total"]]
                    )
                    last_day, last_day_total = list(
                        df[df["date"] == df["date"].max()].iloc[-1][["date", "total"]]
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
                    dragmode="pan",
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=-0.3,
                        xanchor="center",
                        x=0.5,
                    ),
                )
                st.plotly_chart(fig, use_container_width=True, key=f"plotly{key}")
            except Exception as e:
                st.error(f"Error displaying plot: {str(e)}")


if __name__ == "__main__":
    main()
