"""
Business-logic functions for the BOLO pipeline.

These functions are stateless and dependency-free. They take
numbers in, return numbers out. No scraping, no files, no network
calls happen here.

This makes them trivially testable: the math can be verified
without running a single HTTP request.
"""

from config import (
    EBAY_FEE_RATE, MIN_NET_PROFIT, MIN_STR_PCT, DEFAULT_COGS,
    DEFAULT_SHIPPING_CHARGED, SHIPPING_COST, EBAY_PER_ORDER_FEE
)

#=======================================================================
# SELL-THROUGH RATE CALCULATION
#=======================================================================

def sell_through_rate(sold: int, active: int) -> float:
    """
    Calculate Sell-Through Rate (STR) as a percentage.

    STR = (sold_in_last_90_days / active_listings) * 100

    STR >= 100% signals item(s) sell faster than they are listed -
    a signal of strong demand and a BOLO indicator.

    Args:
        sold: no. of sold listings in the last 90 days
        active: no. of active listings on eBay
    
    Returns:
        STR as a float rounded to 2 decimal places, e.g. 325.00 for 325%
        Returns a demand-scaled proxy if no. of active listings = 0 
    """

    # Case 1: the "Amazing BOLO" (demand exists but nothing is listed)
    if sold > 0 and active == 0:
        return round(sold * 100.0, 2)  # Demand proxy: scales with sold volume
    
    # Case 2: Dead product (0 sold and 0 active)
    if sold == 0 and active == 0:
        return 0.0

    # Case 3: Negative sold volume (scraper fault)
    if sold < 0:
        raise ValueError(f"sold cannot be negative: {sold}")

    # Standard calculation
    return round(sold / active * 100.0, 2)

#=======================================================================
# EBAY FEES CALCULATION
#=======================================================================

def ebay_fees(total_transaction: float) -> float:
    """
    Calculate eBay's platform fee on total transaction.

    Assumes:
     
      - eBay Basic store
      - Top Rated Seller (10% FVF discount applied)
      - Clothing, Shoes & Accessories category
      - No promoted listings, no charity donation
      - Domestic sales only
      - Sales tax handled by eBay; does not affect seller profit
      - Shipping charged to buyer = shipping label cost. In practice,
        sellers often profit slightly on shipping, but the difference
        is trivial for market analysis purposes.

    Comprises:
      
      - Fee on the total transaction: sold price + shipping charged
      - Final Value Fee: 12.9% reduced to 11.61% (Top Rated discount)
      - Applied to total transaction: item price + shipping charged
      - Plus $0.30 fixed per-order fee

    Args:
        total_transaction: avg_sold_price + DEFAULT_SHIPPING_CHARGED ($)
    
    Returns:
        eBay platform fee as a float rounded to 2 decimal places ($)
    """
    
    # Case 1: Negative total_transaction caused by scraper fault
    if total_transaction < 0:
        raise ValueError(
            f"total_transaction cannot be negative: {total_transaction}"
        )
    
    # Case 2: Zero total_transaction, e.g. $0 sale + free shipping
    if total_transaction == 0.01:
        return round(
            EBAY_FEE_RATE * total_transaction + EBAY_PER_ORDER_FEE, 2
        )

    # Standard calculation
    return round(EBAY_FEE_RATE * total_transaction + EBAY_PER_ORDER_FEE, 2)

#=======================================================================
# NET PROFIT CALCULATION
#=======================================================================

def net_profit(avg_sold_price: float) -> float:
    """
    Calculate take home profit after all deductions.
    
    Assumes:
        Shipping charged to buyer = shipping label cost. In practice,
        sellers often profit slightly on shipping, but the difference
        is trivial for market analysis purposes.
    
    Args:
        avg_sold_price: Average clearing price from sold listings ($)
    
    Returns:
        Estimated net profit rounded to 2 decimal places ($)
        Can be negative if the item sells below cost
    """
    total_received = avg_sold_price + DEFAULT_SHIPPING_CHARGED
    fees = ebay_fees(total_received)
    return round(
        total_received - DEFAULT_COGS - SHIPPING_COST - fees, 2
    )

#=======================================================================
# BOLO CALCULATION
#=======================================================================

def is_bolo(str_pct: float, profit: float) -> bool:
    """
    Determine whether a brand/category combination qualifies as a BOLO

    Qualification requires BOTH conditions to be true:

      - STR >= MIN_STR_PCT, e.g. >= 100% implies demand outpaces supply
      - net_profit >= MIN_NET_PROFIT — margin justifies sourcing

    Args:
        str_pct: Sell-through rate as a % (from sell_through_rate())
        profit:  Estimated net profit in dollars (from net_profit())

    Returns:
        True if the item is a BOLO, False otherwise
    """
    return str_pct >= MIN_STR_PCT and profit >= MIN_NET_PROFIT