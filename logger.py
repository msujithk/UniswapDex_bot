import time
import datetime
import os
CONNECTION  = 0
ERROR       = 1
OUTPUT      = 2
EXCEPTION   = 3
TRADE       = 4

def write(type,message):
    todays_date = datetime.date.today()
    log_message  = "{}: ".format(time.time()) +  message
    print(message)
    file = None
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    os_path =  ROOT_DIR +  '/OUTPUT/'
    if  not os.path.exists(os_path):
        os.mkdir(os_path)
    if type == CONNECTION:
        file = open(os_path + f'{todays_date}'+ '_' + 'Connection.log', 'at')
    elif type == ERROR:
        file = open(os_path + f'{todays_date}'+ '_' + 'Errors.log', 'at')
    elif type == OUTPUT:
        file = open(os_path + f'{todays_date}'+ '_' + 'Output.log', 'at')
    elif type ==  EXCEPTION:
        file = open(os_path + f'{todays_date}' + '_' + 'EXCEPTIO.log', 'at')
    elif type ==  TRADE:
        file = open(os_path + 'Trade.log', 'at')
    file.write(log_message + "\n")
    file.close()




