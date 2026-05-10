# Assumptions

- The Trading 212 Public API documentation at https://docs.trading212.com/api
  is the reference for broker endpoints. Unsupported or unclear broker
  capabilities are isolated behind adapter TODOs.
- No account size is assumed. Sleeve controls and risk limits are expressed
  as percentages.
- Live trading is disabled by default and requires explicit human arming.
- yfinance, Alpha Vantage, and FMP are convenience feeds, not official
  point-in-time truth layers.
- UK event adapters are validation-oriented starter implementations, not
  a real-time news feed.
- The default smoke-test dataset is synthetic and exists only to validate
  the pipeline.
