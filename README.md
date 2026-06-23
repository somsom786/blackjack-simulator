# Blackjack Simulator & PnL Lab

A browser-based blackjack table and Monte Carlo simulation toolkit built with
vanilla JavaScript and Python. The project combines an interactive fake-money
experience with reproducible PnL analysis, making it possible to explore game
rules, basic strategy, bankroll variance, and betting-model outcomes without
connecting to a casino or using real money.

## Highlights

- Interactive blackjack table with a fake `$1,000` starting bankroll
- Animated dealing, dealer hole-card reveal, chips, and hand transitions
- Six-deck shoe with dealer standing on soft 17
- Blackjack pays `3:2`
- Hit, stand, double, and split support
- Up to four split hands, double after split, and split-ace handling
- Context-aware S17 basic-strategy suggestions
- Session PnL, wins, losses, pushes, blackjacks, and hand history
- Responsive action controls that remain accessible while playing
- Python simulation comparing flat betting with a Hi-Lo betting ramp
- Per-hand CSV export for independent analysis

## Why I Built It

This project explores the difference between short-term outcomes and long-term
expected value. A single profitable session can look convincing while still
being statistical noise, so the Python simulator records every hand and makes
the underlying variance visible.

The browser application focuses on interaction and rules modeling. The Python
tool focuses on deterministic experiments, bankroll accounting, and data
generation. Together they demonstrate frontend state management, domain logic,
simulation design, reproducibility, and structured data export.

## Run the Interactive App

No framework or package installation is required.

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8000/index.html
```

The app is implemented as a self-contained HTML, CSS, and JavaScript project in
`index.html`.

## Run the PnL Simulation

Python 3.10 or newer is recommended. The simulator uses only the standard
library.

```powershell
python blackjack_pnl_sim.py --hands 100000 --seed 42 --unit 1 --bankroll 10000 --out blackjack_results.csv
```

Useful options:

```text
--hands          Number of rounds to simulate
--seed           Random seed for reproducible runs
--unit           Base betting unit
--bankroll       Starting bankroll for each strategy
--penetration    Shoe penetration before reshuffling
--out            CSV output path
--no-csv         Print the summary without writing a CSV
```

Each run compares:

- **Flat betting:** one unit per round
- **Hi-Lo ramp:** one to twelve units based on the true count

Both strategies receive the same simulated cards and use the same playing
strategy, which isolates the effect of bet sizing from random shoe differences.

## CSV Data

The generated dataset includes:

- Round and strategy identifiers
- Starting and ending bankroll
- Bet size and round PnL
- Player and dealer cards
- Recorded player actions
- Result and blackjack status
- Running count, true count, and estimated decks remaining

This makes the output suitable for analysis in Python, Excel, Power BI, or
other data tools.

## Technical Notes

- **Frontend:** semantic HTML, responsive CSS, and dependency-free JavaScript
- **Simulation:** deterministic seeded randomness and explicit S17 strategy
  decision trees
- **Rules engine:** hard/soft hand evaluation, natural blackjacks, doubling,
  splitting, dealer resolution, and bankroll settlement
- **UX:** legal-action states, persistent controls, reduced-motion support, and
  mobile layouts
- **Data:** structured CSV output with round-level auditability

## Responsible Use

This is an educational, fake-money project. It does not connect to Stake.com or
any other gambling service, accept deposits, place real wagers, or claim that a
strategy guarantees profit. Blackjack outcomes remain volatile, and simulated
results should not be treated as financial advice.

## Project Structure

```text
.
|-- index.html              # Interactive fake-money blackjack app
|-- blackjack_pnl_sim.py    # CLI simulation and CSV exporter
`-- README.md
```

## Author

Built by [somsom786](https://github.com/somsom786).

