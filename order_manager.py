"""
Order placement and management functions
"""
import logging
from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)


def place_order(
    kite,
    symbol,
    exchange,
    transaction_type,
    quantity,
    price=None,
    product="MIS",
    order_type="LIMIT",
    validity=None,
    disclosed_quantity=None,
    trigger_price=None,
    squareoff=None,
    stoploss=None,
    trailing_stoploss=None,
    tag=None
):
    """Place order on Zerodha Kite"""
    # Normalise order values to Kite constants
    transaction_map = {
        "BUY": kite.TRANSACTION_TYPE_BUY,
        "SELL": kite.TRANSACTION_TYPE_SELL
    }
    product_map = {
        "CNC": kite.PRODUCT_CNC,
        "MIS": kite.PRODUCT_MIS,
        "NRML": kite.PRODUCT_NRML
    }
    order_type_map = {
        "MARKET": kite.ORDER_TYPE_MARKET,
        "LIMIT": kite.ORDER_TYPE_LIMIT,
        "SL": kite.ORDER_TYPE_SL,
        "SLM": kite.ORDER_TYPE_SLM
    }
    exchange_map = {
        "NSE": kite.EXCHANGE_NSE,
        "BSE": kite.EXCHANGE_BSE,
        "NFO": kite.EXCHANGE_NFO,
        "BFO": kite.EXCHANGE_BFO,
        "CDS": kite.EXCHANGE_CDS,
        "MCX": kite.EXCHANGE_MCX
    }
    
    tx_key = transaction_type.upper() if isinstance(transaction_type, str) else transaction_type
    transaction_value = transaction_map.get(tx_key, transaction_type)
    
    product_key = product.upper() if isinstance(product, str) else product
    product_value = product_map.get(product_key, product)
    
    order_type_key = order_type.upper() if isinstance(order_type, str) else order_type
    order_type_value = order_type_map.get(order_type_key, order_type)
    
    exchange_key = exchange.upper() if isinstance(exchange, str) else exchange
    exchange_value = exchange_map.get(exchange_key, exchange)

    # Zerodha expects None price for market orders
    if order_type_value == kite.ORDER_TYPE_MARKET:
        price_value = None
    else:
        price_value = price
    
    logging.info(
        "Placing order | exchange=%s symbol=%s txn=%s qty=%s product=%s type=%s price=%s",
        exchange_value, symbol, transaction_value, quantity, product_value, order_type_value, price_value
    )
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchange_value,
            tradingsymbol=symbol,
            transaction_type=transaction_value,
            quantity=quantity,
            product=product_value,
            order_type=order_type_value,
            price=price_value,
            validity=validity,
            disclosed_quantity=disclosed_quantity,
            trigger_price=trigger_price,
            squareoff=squareoff,
            stoploss=stoploss,
            trailing_stoploss=trailing_stoploss,
            tag=tag
        )
        logging.info("Order placed successfully: %s", order_id)
        return {"success": True, "order_id": order_id, "message": f"Order placed successfully: {order_id}"}
    except Exception as e:
        error_msg = str(e)
        logging.error("Order placement failed for %s (%s): %s", symbol, exchange_value, error_msg)
        # Extract margin information from error if available
        margin_info = {}
        if "Required margin" in error_msg and "available margin" in error_msg:
            try:
                import re
                required_match = re.search(r'Required margin is ([\d.]+)', error_msg)
                available_match = re.search(r'available margin is ([\d.]+)', error_msg)
                if required_match and available_match:
                    margin_info['required'] = float(required_match.group(1))
                    margin_info['available'] = float(available_match.group(1))
            except:
                pass
        return {"success": False, "order_id": None, "message": error_msg, "margin_info": margin_info}


def execute_order_sequence(kite, order_sequence):
    """
    Execute a list of order instructions sequentially.
    Each order should be a dict containing symbol, exchange, quantity, price,
    and optional product/order_type metadata.
    """
    results = []
    
    for order in order_sequence:
        transaction_type = order.get("transaction_type")
        if transaction_type is None:
            action = (order.get("action") or "").upper()
            transaction_type = "BUY" if action == "BUY" else "SELL"
        
        logging.info(
            "Executing order leg | action=%s market=%s symbol=%s exchange=%s qty=%s price=%s product=%s type=%s",
            order.get("action"),
            order.get("market"),
            order.get("symbol"),
            order.get("exchange"),
            order.get("quantity"),
            order.get("price"),
            order.get("product"),
            order.get("order_type")
        )
        result = place_order(
            kite=kite,
            symbol=order["symbol"],
            exchange=order["exchange"],
            transaction_type=transaction_type,
            quantity=order["quantity"],
            price=order["price"],
            product=order.get("product", "MIS"),
            order_type=order.get("order_type", "LIMIT")
        )
        
        order_report = dict(order)
        order_report["result"] = result
        results.append(order_report)
    
    return results


def place_arbitrage_orders(kite, arbitrage_opportunity, quantity):
    """Place both buy and sell orders for arbitrage opportunity"""
    symbol = arbitrage_opportunity['symbol']
    nse_price = arbitrage_opportunity['nse_price']
    bse_price = arbitrage_opportunity['bse_price']
    higher_exchange = arbitrage_opportunity['higher_exchange']
    lower_exchange = arbitrage_opportunity['lower_exchange']
    
    # Determine which exchange to buy from and which to sell to
    if higher_exchange == 'NSE':
        # Buy from BSE (lower price), Sell on NSE (higher price)
        buy_exchange = 'BSE'
        sell_exchange = 'NSE'
        buy_price = bse_price
        sell_price = nse_price
    else:
        # Buy from NSE (lower price), Sell on BSE (higher price)
        buy_exchange = 'NSE'
        sell_exchange = 'BSE'
        buy_price = nse_price
        sell_price = bse_price
    
    order_sequence = [
        {
            "action": "BUY",
            "market": "CASH",
            "symbol": symbol,
            "exchange": buy_exchange,
            "quantity": quantity,
            "price": buy_price,
            "product": "MIS",
            "order_type": "LIMIT"
        },
        {
            "action": "SELL",
            "market": "CASH",
            "symbol": symbol,
            "exchange": sell_exchange,
            "quantity": quantity,
            "price": sell_price,
            "product": "MIS",
            "order_type": "LIMIT"
        }
    ]
    
    return execute_order_sequence(kite, order_sequence)


def place_cash_futures_orders(
    kite,
    opportunity,
    lots,
    cash_product="CNC",
    futures_product="NRML"
):
    """
    Simplified execution: buy cash first (MARKET), then sell futures (MARKET).
    """
    from config import LOT_SIZE_MAP
    
    symbol = opportunity['symbol']
    cash_price = float(opportunity.get('cash_price') or 0)
    futures_price = float(opportunity.get('futures_price') or 0)
    futures_symbol_raw = opportunity.get('futures_symbol')
    futures_symbol_api = opportunity.get('futures_symbol_api') or futures_symbol_raw
    
    # Lot size and lots - keep it defensive but straightforward
    lot_size = opportunity.get('lot_size') or LOT_SIZE_MAP.get(symbol.upper()) or 1
    try:
        lot_size = int(lot_size)
    except Exception:
        lot_size = 1
    if lot_size < 1:
        lot_size = 1
    
    lots_int = lots or 1
    try:
        lots_int = int(lots_int)
    except Exception:
        lots_int = 1
    if lots_int < 1:
        lots_int = 1
    
    quantity = lot_size * lots_int
    
    order_type_value = "MARKET"
    
    logging.info(
        "Executing cash-futures pair | symbol=%s futures_symbol=%s qty=%s lots=%s lot_size=%s cash_price=%s futures_price=%s order_type=%s",
        symbol, futures_symbol_api, quantity, lots_int, lot_size, cash_price, futures_price, order_type_value
    )
    
    results = []
    
    def fire_order(action, market, exchange, tradingsymbol, price, product):
        order_result = place_order(
            kite=kite,
            symbol=tradingsymbol,
            exchange=exchange,
            transaction_type=action,
            quantity=quantity,
            price=None,
            product=product,
            order_type=order_type_value
        )
        results.append({
            "action": action,
            "market": market,
            "symbol": tradingsymbol,
            "exchange": exchange,
            "quantity": quantity,
            "lots": lots_int,
            "lot_size": lot_size,
            "price": None,
            "result": order_result
        })
        return order_result
    
    fire_order("BUY", "CASH", "NSE", symbol, cash_price, cash_product)
    fire_order("SELL", "FUTURES", "NFO", futures_symbol_api, futures_price, futures_product)
    
    return results

