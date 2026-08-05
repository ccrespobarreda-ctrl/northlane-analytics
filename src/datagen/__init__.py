"""Synthetic data generation for the Northlane Supply Co. analytics project.

Module map:
    config     -- every tunable constant in the project
    catalog    -- product catalog (SCD2 cost history), geography, shipping curves
    customers  -- cohorts, acquisition channels, order calendar
    orders     -- baskets, discounts, landed-cost model and allocation
    returns    -- timing, disposition, reason codes
    marketing  -- campaign spend, CAC inflation, attribution overstatement
    dirty      -- deliberate corruption layer applied on export
"""
