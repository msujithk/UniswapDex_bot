from  uniswap import Uniswap
from binance.client import Client
import time
import logger
import sys
import threading
import pandas as pd 

pub = ''
pvt = ''

ETH_ADDRESS = "0x0000000000000000000000000000000000000000"
ampl = "0xD46bA6D942050d489DBd938a2C909A5d5039A161"
weth_address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
owner = ""
uni_v2_router = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"
yfi = "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e"

token_decimal = 10**18
eth_decimal = 10**9

DEFAULT_BUY_LIMIT = 0.68
DEFAULT_SELL_LIMIT = 0.85
SLIPPAGE = 1

BUY   = 11
SELL  = 22

class Order:
    def __init__(self):
        self.type = None
        self.tx_hash = None
        self.price = 0.0


class UniBot:
    def __init__(self):
        self.client = None
        self.uniswap_wrapper = None
        self.buy_trail = 0.0
        self.sell_trail = 0.0
        self.buy_step = 0.0
        self.sell_step = 0.0
        self.aggregate_price = 0.0
        self.total_qty = 0
        self.order_list = []
        self.fail_count = 0
        self.check_receipt_thread = threading.Thread(target=self.check_receipt)
        self.check_receipt_thread.start() 
        self.create_uniswap_wrapper_and_binance_client()
        self.price_list = []
        price = self.token_price()
        self.buy_limit = price - (price * 0.03)
        logger.write(logger.OUTPUT,f'Constructor: Setting Buy Limit = {self.buy_limit}')
        self.sell_limit = 0
        self.event = threading.Event()
        self.flag1 = False
        self.flag2 = False
        self.flag3 = False
        self.flag4 = False

    def check_receipt(self):
        while True:
            for index in reversed(range(len(self.order_list))):
                order = self.order_list[index]
                logger.write(logger.OUTPUT,f'check_receipt: checking receipt of Hash = { order.tx_hash}')
                receipt =  self.uniswap_wrapper.get_hash_receipt(order.tx_hash)
                if receipt == None:
                    logger.write(logger.OUTPUT,f'check_receipt:receipt not found. Block may not got mined for Hash = {order.tx_hash}')    
                    continue
                if receipt.status == 1:
                    self.fail_count = 0
                    self.event.clear()
                    logger.write(logger.OUTPUT,f'check_receipt: Receipt Received for Hash = {order.tx_hash}')
                    address = None
                    if order.type == BUY:
                       address =  self.uniswap_wrapper.to_checksum_address(yfi)
                    elif order.typr == SELL:
                        address =  self.uniswap_wrapper.to_checksum_address(weth_address)
                    amount = self.get_amount_out(receipt,address)
                    logger.write(logger.OUTPUT,f'check_receipt:Type = {order.type}  Out  amount = {amount}')
                    if order.type == BUY:
                        self.update_buy_data(order, amount)
                    elif order.type == SELL:
                        self.update_sell_data(order,amount)
                        logger.write(logger.TRADE,f'SELL -- YFI Price = {round(order.price,3)} ETH Qty = {amount}') 
                        logger.write(logger.OUTPUT,f'SELL --YFI Price = {round(order.price,3)} ETH Qty = {amount}') 
                    logger.write(logger.OUTPUT,f'check_receipt: Popping order with Hash = {order.tx_hash}')
                    self.order_list.pop(index)

                else:
                    self.event.clear()
                    self.fail_count += 1
                    logger.write(logger.OUTPUT,f'check_receipt: Status = False, Fail count = {self.fail_count}  for  Hash = {order.tx_hash}')
                    if order.type == BUY:
                        price = self.token_price()
                        if self.aggregate_price == 0.0:
                            self.buy_limit = price - (price * 0.02)
                        else:
                            self.buy_limit = self.aggregate_price - (self.aggregate_price  * 0.06)
                        self.buy_trail = 0
                        logger.write(logger.OUTPUT,f'check_receipt: Setting Buy Limit = {self.buy_limit} Buy Trail = {self.buy_trail}')
                    logger.write(logger.OUTPUT,f'check_receipt: Popping order with Failed  Hash = {order.tx_hash}')
                    self.order_list.pop(index)    

            time.sleep(600)


    def get_amount_out(self,receipt,target):
        logs = receipt["logs"] 
        logger.write(logger.OUTPUT,f'get_amount_out: logs = {logs}')
        amount = 0
        for log in logs:
            if target == yfi:
                if log["address"] == yfi:
                    data_in_wei = int(log["data"], 16)
                    amount =  self.uniswap_wrapper.convert_to_token(data_in_wei) 
                    break  
            elif target == weth_address:
                if log["address"] == weth_address:
                    if len(log["topics"]) == 2:
                        data_in_wei = int(log["data"], 16)
                        amount = self.uniswap_wrapper.convert_to_eth(data_in_wei)
                        break
        return amount
            
    

    def create_uniswap_wrapper_and_binance_client(self):
        """ Binance Client"""
        while self.client is None:
            try:
                self.client = Client("", "", {"verify": False, "timeout": 20})
            except Exception:
                logger.write(logger.EXCEPTION,"Re-trying connection to client")
                time.sleep(20)
        """ Uniswap wrapper """
        if len(pvt) < 21:
            sys.exit('Private Key in Empty')

        self.uniswap_wrapper = Uniswap(pub, pvt, '', None, 2, SLIPPAGE)#make trade works with route = 2
        print(self.uniswap_wrapper.get_gas_price())
        sys.exit()

    def token_price(self):
        #eth_price = self.get_eth_price()
        #logger.write(logger.OUTPUT,f'ETH price from binance = {eth_price}')
        token_price_in_base = self.uniswap_wrapper.get_token_price_in_base(owner,self.uniswap_wrapper.to_checksum_address(weth_address),self.uniswap_wrapper.to_checksum_address(yfi),token_decimal)
        #price = round((eth_price * token_price_in_base), 4)
        price = round(token_price_in_base, 5)
        logger.write(logger.OUTPUT,f'Base Price = {price}')
        return price

    def get_eth_price(self):
        info = self.client.get_margin_price_index(symbol = 'ETHUSDT')
        eth_price = float(info['price'])
        return round(eth_price, 2)


    def buy_token(self,amount_in_eth):
        logger.write(logger.OUTPUT,f'buy_token: Preparing to buy {amount_in_eth} ETH worth on YFI')
        return self.uniswap_wrapper.make_trade(ETH_ADDRESS, yfi, amount_in_eth, eth_decimal)

    def get_eth_wallet_balance(self):
        eth_balance = self.uniswap_wrapper.get_eth_wallet_balance()
        logger.write(logger.OUTPUT,f'ETH wallet balance = {eth_balance}')
        return eth_balance

    def get_token_balance(self):
        balance = self.uniswap_wrapper.get_token_balance(self.uniswap_wrapper.to_checksum_address(yfi), token_decimal)
        logger.write(logger.OUTPUT,f'YFI wallet balance = {balance}')
        return balance 

    def sell_token(self, qty_to_sell):
        logger.write(logger.OUTPUT,f'sell_token: Preparing to sell YFI qty = {qty_to_sell}')
        return self.uniswap_wrapper.make_trade(yfi, ETH_ADDRESS, qty_to_sell, token_decimal)

    def reset_data(self):
        self.buy_trail = 0
        self.sell_trail = 0
        self.buy_step = 0
        self.sell_step = 0
        self.flag1 = False
        self.flag2 = False
        self.flag3 = False
        self.flag4 = False

    def get_buy_step(self,price):
        if self.buy_trail == 0:
            self.buy_step = price * 0.03 #3% above current price
        '''
        if price <= 2 and price > 0.96:
            step = 0.05
        elif price <= 0.96 and price > 0.80:
            step = 0.03
        elif price <= 0.80 and price > 0.75:
            step = 0.01
        elif price <= 0.75 and price > 0.70:
            step = 0.02
        else:
            step = 0.02
        '''
        logger.write(logger.OUTPUT,f'get_buy_step: Buy Step = {self.buy_step}')
        return self.buy_step

    def get_sell_percentage(self,price):
        percentage = 1
        '''
        if price >= 0.10 and price < 0.90:
            percentage = 1
        elif price >= 0.90 and price < 0.96:
            percentage = 1
        elif price >= 0.96 and price < 1.06:
            percentage = 0.75
        elif price >= 1.06 and price < 1.15:
            percentage = 0.4
        elif price >= 1.15 and price < 1.25:
            percentage = 0.3
        elif price >= 1.25 and price < 1.50:
            percentage = 0.2
        else:
            percentage = 0.1
        '''
        logger.write(logger.OUTPUT,f'get_sell_percentage: sell percentage = {percentage}')
        return percentage


    def get_step_percentage(self, price):
        gains = self.get_gains(price)
        percent = 0.03
        if 20 >= gains > 0:
            if self.flag1 is False:
                percent = 0.03
                self.flag1 = True
                self.sell_trail = 0
            self.flag2 = False
            self.flag3 = False
            self.falg4 = False
        elif 35 >= gains > 20:
            if self.flag2 is False:
                percent = 0.04
                self.flag2 = True
                self.sell_trail = 0
            self.falg1 = False
            self.falg3 = False
            self.flag4 = False
        elif 50 >= gains > 35:
            if self.flag3 is False:
                percent = 0.05
                self.flag3 = True
                self.sell_trail = 0
            self.flag1 = False
            self.flag2 = False
            self.flag4 = False
        elif 300 >= gains > 50:
            if self.flag4 is False:
                percent = 0.09
                self.flag4 = True
                self.sell_trail = 0
            self.flag1 = False
`           self.flag2 = False
            self.flag3 = False
        return percent
            
            

    def get_sell_step(self,price):
        percentage = self.get_step_percentage(price)
        if self.sell_trail == 0:
            self.sell_step = price * percentage
        '''
        if price >= 0.20 and price < 0.90:
            step = 0.01
        elif price >= 0.90 and price < 0.96:
            step = 0.02
        elif price >= 0.96 and price < 1.06:
            step = 0.05
        elif price >= 1.06 and price < 1.15:
            step = 0.08
        elif price >= 1.15 and price < 1.25:
            step = 0.1
        elif price >= 1.25 and price < 1.50:
            step = 0.15
        else:
            step = 0.45
        '''
        logger.write(logger.OUTPUT,f'get_sell_step: sell step = {self.sell_step}')
        return self.sell_step


    def buy_zone(self,price,buy_step):
        eth_balance = self.get_eth_wallet_balance()
        eth_balance -= 0.25 #reserve some ETH for gas fee
        if eth_balance < 0.3:#2
            logger.write(logger.OUTPUT,f'buy_zone: ETH ballance {eth_balance} in wallet is Low, setting buy retry to max')
            self.buy_trail = 0
            return
        print (f'Buy Zone')
        if self.buy_trail == 0:
            self.buy_trail = price + buy_step
            logger.write(logger.OUTPUT,f'buy_zone:Setting  Buy Trail = {self.buy_trail}')
            return
        if (self.buy_trail - price) > buy_step:
            self.buy_trail -= ((self.buy_trail - price) - buy_step)
            logger.write(logger.OUTPUT,f'buy_zone: Buy Trail = {self.buy_trail}')
        if price >= self.buy_trail:
            if price > self.buy_limit:
                logger.write(logger.OUTPUT,f'buy_zone: price = {price} > {self.buy_limit} buy limit, abandoning buy')
                self.buy_trail = 0
            else:
                eth_in  = 10
                if eth_balance < 10:
                    eth_in = eth_balance
                order = Order()
                order.type = BUY
                order.price = price
                order.tx_hash =  self.buy_token(eth_in)
                logger.write(logger.OUTPUT,f'buy_zone:Hash = {order.tx_hash}')
                self.order_list.append(order)
                logger.write(logger.OUTPUT,f'buy_zone: Appended order to buy order list')
                nxt_buy_percentage = 0.06
                '''
                if price <= 1 and price > 0.85:
                    nxt_buy_percentage = 0.15
                else:
                    nxt_buy_percentage = 0.08
                '''
                self.buy_limit = price - (price * nxt_buy_percentage)# next buy will happen below %
                logger.write(logger.OUTPUT,f'update_buy_data: buy_limit = {self.buy_limit}')
                self.buy_trail = 0
                if len(self.order_list) >= 2:
                    logger.write(logger.OUTPUT,f'update_buy_data: Order_list length > 2, Lot of pending orders in the queue, waiting for 10800 sec')
                    result = self.event.wait(timeout= 10800) 
                    if result is False:
                        logger.write(logger.OUTPUT,f'update_buy_data: Wait timed out')

    def update_sell_data(self, order, amount):
        token_balance = self.get_token_balance()
        if token_balance > (0.10 * self.total_qty):
            logger.write(logger.OUTPUT,f'update_sell_data: Token balance = {token_balance} > {(0.10*self.total_qty)} (0.10*self.total_qty), There Quantities yet to be sold, do not sent Buy Limit')
        else:
            if percent < 1:
                self.sell_trail -= sell_step
                if self.sell_trail < self.sell_limit:
                    self.sell_trail = 0
                logger.write(logger.OUTPUT,f' update_sell_data: Setting sell trail = {self.sell_trail}')
            else:
                self.sell_limit = price * 2
                logger.write(logger.OUTPUT,f'update_sell_data: Setting Sell Limit = { self.sell_limit}')
                self.sell_trail = 0
                self.buy_limit = price - (price * 0.06)
                logger.write(logger.OUTPUT,f' update_sell_data: Setting Buy Limit = {self.buy_limit}')
            


    def update_buy_data(self, order, amount):
        price = order.price
        if amount == 0:
            logger.write(logger.OUTPUT,f' update_buy_data: YFI amount = 0, setting amount = 1')
            amount = 1

        logger.write(logger.TRADE,f'BUY -- YFI Price = {round(order.price,3)} AMPL  Quantity = {amount}')  
        logger.write(logger.OUTPUT,f'BUY --YFI Price = {round(order.price,3)} AMPL  Quantity = {amount}')
        self.aggregate_price = ((price * amount)+(self.aggregate_price * self.total_qty)) / (self.total_qty + amount)
        self.total_qty += amount
        logger.write(logger.OUTPUT,f' update_buy_data(: Aggregate price = {self.aggregate_price} Total quantity  = {self.total_qty}')
        price = self.aggregate_price
        sell_zone_percent = 1.13
        '''
        if price <= 1 and price > 0.90:
            sell_zone_percent = 1.04
        elif price <= 0.90  and price > 0.80:
            sell_zone_percent = 1.05
        elif price <= 0.80 and price > 0.70:
            sell_zone_percent = 1.08
        elif price <= 0.70:
            sell_zone_percent =  1.12
        '''
        self.sell_limit = self.token_price() * sell_zone_percent 
        logger.write(logger.OUTPUT,f'update_buy_data: Sell Zone = {self.sell_limit}')
        
    def get_gains(self, current_price):
        return ((current_price - self.sell_limit)/self.sell_limit) * 100


    def sell_zone(self,price,sell_step):
        print(f'Sell Zone')
        token_balance = self.get_token_balance()
        if (token_balance * price) < 0.2:
            logger.write(logger.OUTPUT,f'sell_zone: YFI balance = { (token_balance * price)} < 0.2, Not enough YFI to sell')
            self.sell_trail = 0
            return
        if self.sell_trail == 0:
            self.sell_trail = price - sell_step
            logger.write(logger.OUTPUT,f'sell_zone: Sell Trail = {self.sell_trail}')
            return
        if (price - self.sell_trail) > sell_step:
            self.sell_trail += ((price - self.sell_trail) - sell_step)
            logger.write(logger.OUTPUT,f'sell_zone: Sell Trail = {self.sell_trail}')
        if price <= self.sell_trail:
            if price < self.sell_limit:
                logger.write(logger.OUTPUT,f'sell_zone: price = {price} < {self.sell_limit} sell limit, abandoning sell')
                self.sell_trail = 0
            else:
                percent = self.get_sell_percentage(price) 
                sell_qty = token_balance  * percent
                if (sell_qty * price)  < 0.2:
                    sell_qty  = token_balance 

                if (sell_qty * price)  < 0.2:
                    logger.write(logger.OUTPUT,f'sell_zone: YFI sell qty = {sell_qty} < 0.2 abandoning sell')
                    self.sell_trail = 0
                    return
                order = Order()
                order.type = SELL
                order.price = price
                order.tx_hash = self.sell_token(sell_qty)
                logger.write(logger.OUTPUT,f'sell_zone: Received hash = {order.tx_hash}')
                self.order_list.append(order)
                logger.write(logger.OUTPUT,f'sell_zone: Sell order appended')
            


    def check_rebase_time(self):
        result = True
        full_time = time.strftime('%H:%M:%S').split(':')
        hour = int(full_time[0])
        logger.write(logger.OUTPUT,f'check_rebase_time: Hour = {hour}')
        if hour >= 2 and hour <= 22:#rebase happens at 2
            result = True
        else:
            logger.write(logger.OUTPUT,f'check_rebase_time: Hour = {hour} Close to Rebase time, halting trade untill hour = 2')
            result = False
        return result


    def check_momentom(self, price):
        if len(self.price_list) > 12:
            self.price_list.pop(0)
        if price > 0:
            self.price_list.append(price) 
        series = pd.Series(self.price_list) 
        diff_percentage = series.pct_change().tolist()    
        weighted_percentage = [diff_percentage[index] * ((index * 100) + 1)  for index in range(0, len(diff_percentage))]
        weighted_percentage.pop(0)
        mom  = sum(weighted_percentage)
        logger.write(logger.OUTPUT,f'momentom = {mom}')
        return  True if mom > 0.0 else False


    def good_to_buy(self, price):
        result = False
        if self.check_momentom(price):
            logger.write(logger.OUTPUT,f'good_to_buy: Upward momentom')
            result = True
        else:
            self.buy_trail = 0
            logger.write(logger.OUTPUT,f'good_to_buy: Downward Momentom.. Buy Trial = {self.buy_trail}')
            result = False
        return result
            


    def main(self):    
        while True:
            price = self.token_price() 
            if price <= self.buy_limit:
                if self.good_to_buy(pruce):
                    buy_step = self.get_buy_step(price)
                    self.buy_zone(price,buy_step)
            elif price >= self.sell_limit:
                sell_step = self.get_sell_step(price)
                self.sell_zone(price,sell_step)
            else:
                print ('Monitoring price ...')
                self.reset_data()

            time,sleep((3 * self.fail_count * 100) + 300)#5mins


if __name__== "__main__":
    print ('Calling Main()')
    unibot = UniBot()
    unibot.main()
