# FinanceSim

## Description

A calculator for simulating financial decisions and comparing different options and projecting future outcomes. Mainly for comparing differing housing options such as buying or renting and allowing one to incorporate as many variables as possible to make the most informed decision.

## Installation

```bash
git clone https://github.com/toastytato/FinanceSim.git
cd FinanceSim
```

## Usage

1. Use the premade Scenarios
2. Create your own Scenarios
    - Insert premade Action sets
    - Create your own Action sets
        - Specify one-time and recurring Actions

## Action Sets

Relevant ones to me

- GetLoan
  - APR (Yearly Interest)
- BuyAndSellHouse
- RefinanceMortgage
- RentOutRoom
- RentApartment
- InvestInStocks

Other

- LeaseCar
- BuyCar

## TODO

1. LLM should be able to generate scenarios
    - There will be a set of predefined Action sets that represent common financial decisions
    - Each of these predefined Action sets will have its own JSON setup associated with it
    - When the LLM is prompted by the user with a request, the LLM will generate the JSON for the combination of Action sets that meets the request
    - If there is a request with Action sets that do not exist, then the LLM will let the user know
    - 


## Scripts for the Different Levels of Abstraction

At the lowest level is the code that makes up the financial sim framework. Here the system executes the desired actions in chronological order and holds the data containers (accounts and rates).
Next, is the creation of singular actions. The actions holds the actual operation that will be performed, when it will happen, and to whom it will affect. This level has the most control over what types of decisions one can make.
Third is the groupings of related actions called Action Groups which allows for common decisions to be abstracted into predefined parameters. This focuses on executing the more common decisions a user might ask the framework. Ideally there is sufficient breadth in the existing Action Groups to formulate more complex decisions. However if an edge case exist, it may be necessary to return to creating custom actions to achieve the result desired. If such is the case, it should be a straightforward task to fold this into the existing database of Action Groups so that a more comprehensive set of decisions can be captured by this database.
Fourth is the structured JSON file, which creates scenario(s) that can be composed of multiple smaller decisions from the Action Groups. These scenarios are typically what the user cares about, and they may want to compare multiple scenarios to understand how the scenario they may decide on will play out financially over some time period.
Lastly is the LLM, which acts as the UI so a user can describe their scenario based on their existing knowledge the financial terms. The LLM can fill in the quantitative values based on the user's qualitative description of their scenario.

In short, the conceptual abstraction goes:

- Action (Data flow and manipulation) -- Low-level framework
- Decision (Multiple Actions) -- Database of decisions
- Scenario (Multiple Decisions) -- Set of decisions
- Comparison (Multiple Scenarios) -- JSON file which holds the scenario(s) and the decision(s) associated with each scenario.
- User (Human request) -- LLM interfaces into JSON file

Possible alternative:

- No JSON, just let the LLM run code straightaway
  - Need additional precautions


  # Chain of events

- Need the bot to return where in the state machine they think they are in, and respond accordingly

  1. Introduce the simulator and offer examples
  2. User describes in their verbage what they want to compare
  3. Bot creates the scenario then asks the user to confirm or modify
  4. If the user confirms, 


What i want
- Bot to create and visualize user financial decisions
  - help user craft their scenario comparisons
  - help assess and make decisions