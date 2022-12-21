import json


def df_to_jqtable(df, formatter=lambda x: x):
    headings = list(df.columns)
    data = [formatter(*[df[c].iloc[i] for c in headings])
            for i in range(len(df))]

    formats = json.dumps({'columnDefs': [{'targets': [i for i in range(1, len(headings))],
                                          'className': 'dt-body-right'}], 'ordering': False})

    return headings, data, formats
