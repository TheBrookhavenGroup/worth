# Worth
Simple trading and cash management bookkeeping system.

## Introduction

### Goal
Keep track of wealth at a collection of brokers and banks across a variety of asset classes.  Do it privately, without storing information on third party servers.  The early releases work with cash, stocks, options, and exchange traded futures contracts. We'll add a variety of portfolio risk metrics and analytics.

## Reasoning
Maybe this isn't so reasonable. Sure, I could have used something off-the-shelf or another open source project.  But, I wanted this to be simple and private.  I did not want my data stored on someone else's server.  Lastly, I wanted to have a code base I could customize easily and add asset classes to.  All that being said I'll surely borrow and use other open source packages from time to time.

This also serves as one of those projects I use to learn new things between other projects.  It was not started after a build vs buy study, although I have looked around a bit, but rather as a fun project to both improve my engineering skills and provide tools for wealth management.  It is simple and sometimes that isn't stupid.

## Stack
Django + Postgres + Pandas + NumPy + Plotly

Trades are entered manually or via brokerage APIs. Market data currently comes from the yahoo API.  I have used the Interactive Brokers API as a real-time market data feed but don't need that yet for this project.  Though it is a fantastic API.

The Stack will grow with added functionality as needed, it is better not to add just for the sake of it.  I'm a stack minimalist for tha sake of clarity and maintainability.  Django is great because it is a complete framework and provides most of the plumbing with lots of experts concerned with security.  I have learned a lot from reading how Django engineers organized the framework.

## PGP
One of my brokers allows me to download monthly statements via ftp.  They recently required those files to be PGP encrypted.  I have added some automation for this so that it is painless to get those statements and decrypt them.  However, from time to time some manual work may be needed and the notes I have [here](pgp.md) could be useful.

## Scripts

The `scripts/tax_manifest.py` script cannot be run from a PyCharm shell because it is sandboxed.
It can be run from a shell outside PyCharm by giving the full path to the script.
