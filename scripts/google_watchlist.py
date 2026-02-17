#!/usr/bin/env python3

import sys
import os
import json
import pickle
import configparser

import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


CONFIG_FILE = os.path.expanduser("~/.worth")
TOKEN_FILE = os.path.expanduser("~/.watchlist_token.pickle")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_google_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if "Google" not in config:
        raise RuntimeError("Missing [Google] section in ~/.worth")

    google = config["Google"]

    if "WATCHLIST_CREDS" not in google:
        raise RuntimeError("WATCHLIST_CREDS not found in ~/.worth")

    if "SPREADSHEET_ID" not in google:
        raise RuntimeError("SPREADSHEET_ID not found in ~/.worth")

    creds_json = google["WATCHLIST_CREDS"]
    spreadsheet_id = google["SPREADSHEET_ID"]

    return json.loads(creds_json), spreadsheet_id


def get_client(client_config):
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return gspread.authorize(creds)


def update_watchlist(ticker: str, shares: float, buy_price: float):
    client_config, spreadsheet_id = get_google_config()
    client = get_client(client_config)

    sheet = client.open_by_key(spreadsheet_id).sheet1

    ticker = ticker.upper().strip()
    rows = sheet.get_all_values()

    # If ticker exists → update Shares & Buy Price only
    for idx, row in enumerate(rows[1:], start=2):
        if row and row[0].strip().upper() == ticker:
            sheet.update(
                f"B{idx}:C{idx}", [[shares, buy_price]], value_input_option="USER_ENTERED"
            )
            print(f"Updated {ticker}")
            return

    # If ticker not found → append new row with formulas
    new_row = len(rows) + 1

    sheet.append_row(
        [
            ticker,
            shares,
            buy_price,
            f"=GOOGLEFINANCE(A{new_row})",
            f"=B{new_row}*D{new_row}",
            f"=B{new_row}*(D{new_row}-C{new_row})",
        ],
        value_input_option="USER_ENTERED",
    )

    print(f"Added {ticker}")


def main():
    if len(sys.argv) != 4:
        print("Usage: google_watchlist TICKER SHARES BUY_PRICE")
        sys.exit(1)

    ticker = sys.argv[1]
    shares = float(sys.argv[2])
    buy_price = float(sys.argv[3])

    update_watchlist(ticker, shares, buy_price)


if __name__ == "__main__":
    main()
