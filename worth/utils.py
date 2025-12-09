import json

nicer_headings = {
    "a": "Account",
    "t": "Ticker",
    "q": "Quantity",
    "wap": "WAP",
    "cs": "CS",
    "price": "Price",
    "pnl": "PnL",
    "position": "Position",
}


def nice_headings(h):
    def get_nicer_heading(h):
        try:
            return nicer_headings[h]
        except KeyError:
            return h

    return [get_nicer_heading(i) for i in h]


def df_to_jqtable(df, formatter=lambda x: x):
    headings = list(df.columns)
    data = [formatter(*[df[c].iloc[i] for c in headings]) for i in range(len(df))]

    formats = json.dumps(
        {
            "columnDefs": [
                {
                    "targets": [i for i in range(1, len(headings))],
                    "className": "dt-body-right",
                }
            ],
            "ordering": True,
            "pageLength": 100,
        }
    )

    return headings, data, formats
