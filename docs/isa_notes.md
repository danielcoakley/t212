# ISA Operational Notes

These are cautious operational notes for system design. They are not
personal tax advice.

- The starter is long-only, cash-funded, and does not implement margin,
  shorting, derivatives, CFDs, or leverage.
- Instrument eligibility should be checked against the authenticated
  Trading 212 Stocks and Shares ISA universe before any live order.
- UK Stamp Duty Reserve Tax is modelled as a configurable purchase-side
  rule for applicable UK shares, with instrument-level overrides.
- US dividends may have withholding tax depending on instrument, treaty
  paperwork, and broker handling. The smoke-test default is disabled and
  the assumption is configurable for backtests.
- Losses inside an ISA are not treated like taxable-account capital
  losses. Do not build strategy logic that assumes taxable loss use.
- Trading costs, spreads, FX, stamp duty, levies, and operational errors
  can matter more than tax inside an ISA.
