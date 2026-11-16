# international-rate-of-capital-app
This app will calculate the international rate of capital

# International Cost of Capital Comparison App

A Streamlit web application that computes and compares a project's Cost of Equity ($K_e$), Cost of Debt ($K_d$), and Weighted Average Cost of Capital (WACC) in both U.S. Dollars (USD) and the local currency of any selected target country.

## Data Sources
- **U.S. Industry Betas (Unlevered)**: Prof. Aswath Damodaran (Stern NYU) - `betas.xls`
- **U.S. BBB Borrowing Spread**: Prof. Aswath Damodaran (Stern NYU) - Ratings & Spreads table (Baa2/BBB for non-financial service firms)
- **Corporate Statutory Tax Rates**: OECD Corporate Tax Statistics (2024 report)
- **10-Year Sovereign Bond Yields**: Trading Economics / Sovereign Debt Benchmarks

## Features
- **Dynamic Live Fetch & Offline Fallback**: Fetches live data with automatic fallbacks so the app never fails if remote endpoints block web scrapers.
- **Side-by-Side Comparison**: Direct metric and tabular comparison between USD and Foreign currency capital costs.
- **Manual Overrides**: Toggle and modify unlevered beta, tax rates, borrowing spreads, and bond yields.
- **Interactive All-Industry Benchmark**: Chart and table comparing WACC across all Damodaran industries.
- **Data Export**: One-click download of project parameters and results to CSV.

## How to Run Locally
1. Clone this repository:
   ```bash
   git clone [suspicious link removed]
   cd international-wacc-app
