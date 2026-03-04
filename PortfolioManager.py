# Description: This script updates a portfolio markdown note in Obsidian with
# current market data from Yahoo Finance. It calculates performance metrics, 
# generates buy/sell signals, and creates a performance chart that is embedded
# in the note. The script is designed to be run periodically to keep the 
# portfolio information up-to-date.
# Author: Alberto Marrero
# Date: March 2026

import pandas as pd
import yfinance as yf
import re
import io
import os
from datetime import datetime
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
OBSIDIAN_NOTE_PATH = "C:\\Vaults\\JamsVault\\009 Banca e inversión\\My Portfolio.md"
OBSIDIAN_ASSETS_PATH = "C:\\Vaults\\JamsVault\\000 Assets"
TITLE_PORTFOLIO_SECTION = "Portfolio"
TITLE_SUMMARY_SECTION = "Portfolio Summary"
THRESHOLD_BUY = 1.33  # 33% above purchase price
THRESHOLD_SELL = 0.75  # 25% below peak price

def generate_performance_chart(df, folder_path, update_date):
    """Generates a performance and allocation chart."""
    # Filter out cash if you only want to see securities
    plot_df = df.copy()
    
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Bar chart for Weights
    color_weight = '#a8dadc'
    ax1.set_xlabel('Security')
    ax1.set_ylabel('Portfolio Weight (%)', color='#457b9d')
    bars = ax1.bar(plot_df['Name'], plot_df['Weight (%)'], color=color_weight, alpha=0.7, label='Weight %')
    ax1.tick_params(axis='y', labelcolor='#457b9d')
    plt.xticks(rotation=45, ha='right')

    # Line chart for Performance %
    ax2 = ax1.twinx()
    color_perf = '#e63946'
    ax2.set_ylabel('Performance in CHF (%)', color=color_perf)
    ax2.plot(plot_df['Name'], plot_df['Performance (P/L) in CHF in %'], color=color_perf, marker='o', linewidth=2, label='Perf %')
    ax2.tick_params(axis='y', labelcolor=color_perf)
    
    # Add a horizontal line at 0%
    ax2.axhline(0, color='black', linestyle='--', linewidth=0.8)

    plt.title(f'Portfolio Status - {update_date}')
    fig.tight_layout()
    
    chart_filename = f"portfolio_chart_{update_date}.png"
    chart_path = os.path.join(folder_path, chart_filename)
    plt.savefig(chart_path)
    plt.close()
    return chart_filename

def get_exchange_rate(from_curr, to_curr="CHF"):
    if from_curr == to_curr: return 1.0
    try:
        ticker = f"{from_curr}{to_curr}=X"
        data = yf.Ticker(ticker).history(period="1d")
        return data['Close'].iloc[-1]
    except:
        print(f"Error fetching FX rate for {from_curr}. Using 1.0 as fallback.")
        return 1.0

def extract_section(content, section_name):
    """Extracts text under a specific markdown header."""
    pattern = rf"## {section_name}\n(.*?)(?=\n##|$)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""

def get_summary_value(summary_text, key):
    """Finds a numeric value for a given key in the summary text."""
    match = re.search(rf"{key}[:\s]*([\d,.]+)", summary_text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 0.0

def run_update():
    if not os.path.exists(OBSIDIAN_NOTE_PATH):
        print(f"File not found: {OBSIDIAN_NOTE_PATH}")
        return

    note_folder = os.path.dirname(OBSIDIAN_NOTE_PATH)
    
    with open(OBSIDIAN_NOTE_PATH, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # 1. Parse Sections
    portfolio_section = extract_section(full_content, TITLE_PORTFOLIO_SECTION)
    summary_section = extract_section(full_content, TITLE_SUMMARY_SECTION)

    # 2. Extract Table and Cash
    table_match = re.search(r'(\|.*\|(?:\n\|.*\|)*)', portfolio_section)
    if not table_match:
        print("Table not found in Portfolio section.")
        return
    
    table_raw = table_match.group(1)
    lines = table_raw.strip().split('\n')
    data_lines = [l for l in lines if not re.match(r'^\|[:\s-]*\|', l)]
    df = pd.read_csv(io.StringIO('\n'.join(data_lines).replace('|', ',')), sep=',').iloc[:, 1:-1]
    df.columns = [c.strip() for c in df.columns]

    cash_chf = get_summary_value(summary_section, "Cash CHF")
    cash_eur = get_summary_value(summary_section, "Cash EUR")
    cash_usd = get_summary_value(summary_section, "Cash USD")

    # 3. User Prompts
    do_update = input("Update portfolio with current market data? (y/n): ").lower() == 'y'
    if not do_update: return

    do_deep_scan = input("Perform deep scan for historical Max/Min prices since purchase? (y/n): ").lower() == 'y'

    # 4. Fetch Market Data & Process
    print("Connecting to Yahoo Finance...")
    usd_chf = get_exchange_rate("USD", "CHF")
    eur_chf = get_exchange_rate("EUR", "CHF")
    fx_map = {"USD": usd_chf, "EUR": eur_chf, "CHF": 1.0}
    
    today = datetime.now().strftime("%Y-%m-%d")
    signals = []
    total_market_val_chf = 0
    total_purchase_val_chf = 0

    for idx, row in df.iterrows():
        ticker_symbol = str(row['Ticker']).strip()
        print(f"Processing {ticker_symbol}...")
        stock = yf.Ticker(ticker_symbol)
        curr = row['Currency'].strip()
        fx = fx_map.get(curr, 1.0)
        
        # Deep Scan or Single Day Fetch
        if do_deep_scan:
            start_date = str(row['Purchase date']).strip()
            hist = stock.history(start=start_date)
            if not hist.empty:
                # Update Max
                new_max_price = round(hist['Close'].max(), 2)
                new_max_date = hist['Close'].idxmax().strftime("%Y-%m-%d")
                df.at[idx, 'Maximum close price'] = new_max_price
                df.at[idx, 'Maximum close date'] = new_max_date
                
                # Update Min
                new_min_price = round(hist['Close'].min(), 2)
                new_min_date = hist['Close'].idxmin().strftime("%Y-%m-%d")
                df.at[idx, 'Minimum close price'] = new_min_price
                df.at[idx, 'Minimum close date'] = new_min_date
                
                new_close = round(hist['Close'].iloc[-1], 2)
            else:
                print(f"No history found for {ticker_symbol}")
                continue
        else:
            hist = stock.history(period="1d")
            new_close = round(hist['Close'].iloc[-1], 2)
            
            # Incremental Max/Min Update
            if new_close > float(row['Maximum close price']):
                df.at[idx, 'Maximum close price'], df.at[idx, 'Maximum close date'] = new_close, today
            if new_close < float(row['Minimum close price']):
                df.at[idx, 'Minimum close price'], df.at[idx, 'Minimum close date'] = new_close, today

        # Standard Updates
        df.at[idx, 'Last close price'], df.at[idx, 'Last close date'] = new_close, today
        
        qty = float(row['Quantity'])
        buy_price = float(row['Purchase price'])
        mkt_val = qty * new_close
        df.at[idx, 'Market value'] = round(mkt_val, 2)
        
        perf = mkt_val - (qty * buy_price)
        df.at[idx, 'Performance (P/L) in security currency'] = round(perf, 2)
        df.at[idx, 'Performance (P/L) in CHF'] = round(perf * fx, 2)
        df.at[idx, 'Performance (P/L) in security currency in %'] = round((new_close/buy_price - 1)*100, 2)
        df.at[idx, 'Performance (P/L) in CHF in %'] = round((new_close/buy_price - 1)*100, 2)

        total_market_val_chf += (mkt_val * fx)
        total_purchase_val_chf += (qty * buy_price * fx)

        # Signal Logic
        if new_close >= buy_price * THRESHOLD_BUY:
            signals.append(f"🟢 **BUY SIGNAL**: {row['Name']} ({ticker_symbol}) is 33% above purchase.")
        if new_close <= float(df.at[idx, 'Maximum close price']) * THRESHOLD_SELL:
            signals.append(f"🔴 **SELL SIGNAL**: {row['Name']} ({ticker_symbol}) is 25% below its peak.")

    # 5. Global Totals
    total_value_chf = total_market_val_chf + cash_chf + (cash_eur * eur_chf) + (cash_usd * usd_chf)
    total_perf_chf = total_market_val_chf - total_purchase_val_chf
    total_perf_pct = (total_perf_chf / total_purchase_val_chf) * 100 if total_purchase_val_chf != 0 else 0

    # Update Weights
    for idx, row in df.iterrows():
        val_chf = row['Market value'] * fx_map.get(row['Currency'].strip(), 1.0)
        df.at[idx, 'Weight (%)'] = round((val_chf / total_value_chf) * 100, 2)
        
    # --- NEW: CHART GENERATION ---
    print("Generating performance chart...")
    chart_file = generate_performance_chart(df, note_folder, today)

    # 6. Reconstruct Note
    new_table = df.to_markdown(index=False)
    
    # Updated Summary Header
    new_summary = (
        f"Update date: {today}\n"
        f"Total value in CHF: {total_value_chf:,.2f}\n"
        f"Cash CHF: {cash_chf:,.2f}\n"
        f"Cash EUR: {cash_eur:,.2f}\n"
        f"Cash USD: {cash_usd:,.2f}\n"
        f"Total performance (P/L) in CHF: {total_perf_chf:,.2f}\n"
        f"Total performance (P/L) in CHF in %: {total_perf_pct:.2f}%"
    )

    # Updated Signal/Update Section with Image Embed
    signal_entry = f"\n## {today} Portfolio update\n"
    signal_entry += f"![[{chart_file}]]\n\n"  # This embeds the chart in Obsidian
    signal_entry += f"**Total Performance:** {total_perf_chf:,.2f} CHF ({total_perf_pct:.2f}%)\n\n"
    signal_entry += "\n".join(signals) if signals else "No buy/sell signals today."
    signal_entry += "\n---"

    # Replace and Save
    updated_content = full_content.replace(table_raw, new_table)
    if summary_section:
        updated_content = updated_content.replace(summary_section, new_summary)
    updated_content += signal_entry

    with open(OBSIDIAN_NOTE_PATH, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"Update successful! Chart saved as {chart_file}")

if __name__ == "__main__":
    run_update()