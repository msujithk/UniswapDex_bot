from  uniswap import Uniswap
from binance.client import Client
import time
import logger
import sys
import threading
pub = ''
pvt = ''

ETH_ADDRESS = "0x0000000000000000000000000000000000000000"
ampl = "0xD46bA6D942050d489DBd938a2C909A5d5039A161"
weth_address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
owner = ""
uni_v2_router = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"

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
        self.buy_limit  =  DEFAULT_BUY_LIMIT
        self.sell_limit = DEFAULT_SELL_LIMIT
        self.buy_trail = 0
        self.sell_trail = 0
        self.ampl_aggregate_price = 0.0
        self.ampl_total_qty = 0
        self.order_list = []
        self.create_uniswap_wrapper_and_binance_client()
        self.check_receipt_thread = threading.Thread(target=self.check_receipt)
        self.check_receipt_thread.start() 
    

    def check_receipt(self):
        #order = Order()
        #order.type = BUY
        #order.tx_hash = ''
        #self.order_list.append(order)
        order=Order()
        order.type =BUY
        order.tx_hash=''
        self.order_list.append(order)
        while True:
            logger.write(logger.OUTPUT,f'check_receipt: ENTERING WHILE')
            for index in reversed(range(len(self.order_list))):
                order = self.order_list[index]
                logger.write(logger.OUTPUT,f'check_receipt: checking receipt of Hash = { order.tx_hash}')
                receipt =  self.uniswap_wrapper.get_hash_receipt(order.tx_hash)
                if receipt == None:
                    logger.write(logger.OUTPUT,f'check_receipt:receipt == None,  Failed getting receipt for Hash = {order.tx_hash}')
                    continue
                if receipt.status == 1:
                    logger.write(logger.OUTPUT,f'check_receipt: Receipt Received for Hash = {order.tx_hash}')
                    address = None
                    if order.type == BUY:
                       address =  self.uniswap_wrapper.to_checksum_address(ampl)
                    elif order.typr == SELL:
                        address =  self.uniswap_wrapper.to_checksum_address(weth_address)
                    amount = self.get_amount_out(receipt,address)
                    logger.write(logger.OUTPUT,f'check_receipt:Type = {order.type}  Out  amount = {amount}')
                    if order.type == BUY:
                        self.update_buy_data(order, amount)
                    elif order.type == SELL:
                        logger.write(logger.TRADE,f'SELL -- AMPL Price = {round(order.price,3)} ETH Qty = {amount}') 
                        logger.write(logger.OUTPUT,f'SELL -- AMPL Price = {round(order.price,3)} ETH Qty = {amount}') 
                    logger.write(logger.OUTPUT,f'check_receipt: Popping order with Hash = {order.tx_hash}')
                    self.order_list.pop(index)

                else:
                    logger.write(logger.OUTPUT,f'check_receipt: Failed getting receipt for Hash = {order.tx_hash}')
                
            time.sleep(10)
        logger.write(logger.OUTPUT,f'check_receipt: RECEIPT THREAD EXITED')

    def get_amount_out(self,receipt,target):
        logs = receipt["logs"] 
        logger.write(logger.OUTPUT,f'get_amount_out: logs = {logs}')
        amount = 0
        for log in logs:
            if target == ampl:
                if log["address"] == ampl:
                    data_in_wei = int(log["data"],16)
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

    def ample_price(self):
        eth_price = self.get_eth_price()
        logger.write(logger.OUTPUT,f'ETH price from binance = {eth_price}')
        token_price_in_eth = self.uniswap_wrapper.get_token_price_in_eth(owner,weth_address,ampl)
        price = round((eth_price * token_price_in_eth), 4)
        logger.write(logger.OUTPUT,f'AMPL Price = {price}')
        return price

    def get_eth_price(self):
        info = self.client.get_margin_price_index(symbol = 'ETHUSDT')
        eth_price = float(info['price'])
        return round(eth_price, 2)


    def buy_ampl(self,amount_in_eth):
        logger.write(logger.OUTPUT,f'buy_ampl: Preparing to buy {amount_in_eth} ETH worth on AMPL')
        return self.uniswap_wrapper.make_trade(ETH_ADDRESS, ampl, amount_in_eth)

    def get_eth_wallet_balance(self):
        eth_balance = self.uniswap_wrapper.get_eth_wallet_balance()
        logger.write(logger.OUTPUT,f'ETH wallet balance = {eth_balance}')
        return eth_balance

    def get_ample_wallet_balance(self):
        ample_balance = self.uniswap_wrapper.get_ampl_wallet_balance(ampl)
        logger.write(logger.OUTPUT,f'Ample wallet balance = {ample_balance}')
        return ample_balance 

    def sell_ampl(self, ample_qty_to_sell):
        logger.write(logger.OUTPUT,f'sell_ampl: Preparing to sell ample qty = {ample_qty_to_sell}')
        return self.uniswap_wrapper.make_trade(ampl, ETH_ADDRESS, ample_qty_to_sell)

    def reset_data(self):
        self.buy_trail = 0
        self.sell_trail = 0

    def get_buy_step(self,price):
        step = 0.02
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
        logger.write(logger.OUTPUT,f'get_buy_step: step = {step}')
        return step

    def get_sell_percentage(self,price):
        percentage = 1
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
        logger.write(logger.OUTPUT,f'get_sell_percentage: sell percentage = {percentage}')
        return percentage




    def get_sell_step(self,price):
        step = 0.01
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
        logger.write(logger.OUTPUT,f'get_sell_step: sell step = {step}')
        return step


    def buy_zone(self,price,buy_step):
        eth_balance = self.get_eth_wallet_balance()
        eth_balance -= 0.25 #reserve some ETH for gas fee
        if eth_balance < 0.3:
            logger.write(logger.OUTPUT,f'buy_zone: ETH ballance {eth_balance} in wallet is Low, setting buy retry to max')
            self.buy_trail = 0
            return
        print (f'Buy Zone')
        if self.buy_trail == 0:
            self.buy_trail = price + buy_step
            logger.write(logger.OUTPUT,f'buy_zone: Buy Trail = {self.buy_trail}')
            return
        if (self.buy_trail - price) > buy_step:
            self.buy_trail -= ((self.buy_trail - price) - buy_step)
            logger.write(logger.OUTPUT,f'buy_zone: Buy Trail = {self.buy_trail}')
        if price >= self.buy_trail:
            if price > self.buy_limit:
                logger.write(logger.OUTPUT,f'buy_zone: price = {price} > {self.buy_limit} buy limit, abandoning buy')
                self.buy_trail = 0
            else:
                eth_in  = 0
                if eth_balance < 1:
                    eth_in = eth_balance
                elif eth_balance >= 1 and eth_balance < 4:
                    eth_in = round(eth_balance / 2, 3)
                elif eth_balance >= 4 and eth_balance < 6:
                    eth_in = round(eth_balance / 3, 3)
                else:
                    eth_in = round(eth_balance / 4, 3)
                order = Order()
                order.type = BUY
                order.price = price
                order.tx_hash =  self.buy_ampl(eth_in)
                logger.write(logger.OUTPUT,f'buy_zone:Hash = {order.tx_hash}')
                self.order_list.append(order)
                logger.write(logger.OUTPUT,f'buy_zone: Appended order to buy order list')
                nxt_buy_percentage = 0.1
                if price <= 1 and price > 0.85:
                    nxt_buy_percentage = 0.15
                else:
                    nxt_buy_percentage = 0.08

                self.buy_limit = price - (price * nxt_buy_percentage)# next buy will happen below %
                logger.write(logger.OUTPUT,f'update_buy_data: buy_limit = {self.buy_limit}')


    def update_buy_data(self, order, amount):
        price = order.price
        if amount == 0:
            logger.write(logger.OUTPUT,f' update_buy_data: ample amount = 0, setting amount = 1')
            amount = 1

        logger.write(logger.TRADE,f'BUY -- AMPL Price = {round(order.price,3)} AMPL  Quantity = {amount}')  
        logger.write(logger.OUTPUT,f'BUY -- AMPL Price = {round(order.price,3)} AMPL  Quantity = {amount}')
        self.ampl_aggregate_price = ((price * amount)+(self.ampl_aggregate_price * self.ampl_total_qty)) / (self.ampl_total_qty + amount)
        self.ampl_total_qty += amount
        logger.write(logger.OUTPUT,f' update_buy_data(: Aggregate price = {self.ampl_aggregate_price} Total quantity  = {self.ampl_total_qty}')
        price = self.ampl_aggregate_price
        sell_zone_percent = 1.04
        if price <= 1 and price > 0.90:
            sell_zone_percent = 1.04
        elif price <= 0.90  and price > 0.80:
            sell_zone_percent = 1.05
        elif price <= 0.80 and price > 0.70:
            sell_zone_percent = 1.08
        elif price <= 0.70:
            sell_zone_percent =  1.12
        self.sell_limit = self.ample_price() * sell_zone_percent 
        logger.write(logger.OUTPUT,f'update_buy_data: Sell Zone = {self.sell_limit}')
        


    def sell_zone(self,price,sell_step):
        print(f'Sell Zone')
        ampl_balance = self.get_ample_wallet_balance()
        if (ampl_balance * price) < 15:
            logger.write(logger.OUTPUT,f'sell_zone: AMPL value = { (ampl_balance * price)} < 15, Not enough ample to sell')
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
                ampl_balance = self.get_ample_wallet_balance()
                ample_sell_qty = ampl_balance  * self.get_sell_percentage(price) 
                if ample_sell_qty  < 15:
                    ample_sell_qty  = ampl_balance 

                if ample_sell_qty  < 15:
                    logger.write(logger.OUTPUT,f'sell_zone: AMPL sell qty = {ample_sell_qty} < 15, abandoning sell')
                    self.sell_trail = 0
                    return
                order = Order()
                order.type = SELL
                order.price = price
                order.tx_hash = self.sell_ampl(ample_sell_qty)
                logger.write(logger.OUTPUT,f'sell_zone: Received hash = {order.tx_hash}')
                self.order_list.append(order)
                logger.write(logger.OUTPUT,f'sell_zone: Sell order appended')
                self.sell_trail -= sell_step
                if self.sell_trail < self.sell_limit:
                    self.sell_trail = 0
                logger.write(logger.OUTPUT,f'sell_zone: Setting sell trail = {self.sell_trail}')
                self.buy_limit = DEFAULT_BUY_LIMIT
                logger.write(logger.OUTPUT,f'sell_zone: Setting Buy Limit = {self.buy_limit}')
            

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



    def main(self):    
        while True:
            print ('Main loop')
            time.sleep(5) #5mins
            continue
            price = self.ample_price() 
            if price <= self.buy_limit:
                if self.check_rebase_time():
                    buy_step = self.get_buy_step(price)
                    self.buy_zone(price,buy_step)
                else:
                    self.buy_trail = 0
            
            elif price >= self.sell_limit:
                sell_step = self.get_sell_step(price)
                self.sell_zone(price,sell_step)
            else:
                print ('Monitoring price ...')
                self.reset_data()

            time.sleep(5) #5mins

if __name__== "__main__":
    print ('Calling Main()')
    unibot = UniBot()
    unibot.main()
