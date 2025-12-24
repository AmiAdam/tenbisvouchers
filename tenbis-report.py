import requests
import os 
import pickle
import urllib3
import json
from datetime import date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
CWD=os.getcwd()
SESSION_PATH = f"{CWD}/sessions.pickle"
TOKEN_PATH = f"{CWD}/usertoken.pickle"
FILENAME = f"report-{date.today().strftime('%d-%b-%Y')}.html"
OUTPUT_PATH = f"{CWD}/{FILENAME}"
TENBIS_FQDN = "https://www.10bis.co.il"
DEBUG = False

RES_ID_SHEFA = 45915


HTML_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ font-family: 'Heebo', sans-serif !important; box-sizing: border-box; }}
        body {{ margin: 10px auto; max-width: 95%; background-color: white; }}
        table {{ width: 100%; border-collapse: collapse; border: 1px solid #dee2e6; }}
        th {{ 
            background-color: #f8f9fa; 
            border: 1px solid #dee2e6; 
            padding: 10px 5px; 
            text-align: right; 
            font-weight: 800; 
            font-size: 14px;
            color: #0a3847;
        }}
        td {{ 
            border: 1px solid #dee2e6; 
            padding: 8px 5px; 
            vertical-align: middle; 
            font-size: 14px;
        }}
        h1 {{ font-size: 20px; color: #FF8100; border-bottom: 3px solid #FF8100; padding-bottom: 5px; margin-bottom: 10px; }}
        @media print {{ body {{ margin: 0; max-width: 100%; }} tr {{ page-break-inside: avoid; }} }}
    </style>
</head>
<body>
    <h1>ריכוז תווי קנייה - שפע ברכת השם</h1>
    <table>
        <thead>
            <tr>
                <th style="width: 35px; text-align: center;">#</th>
                <th style="width: 18%;">חנות</th>
                <th style="width: 13%;">תאריך</th>
                <th style="width: 18%;">מספר תו</th>
                <th style="width: 12%;">סכום</th>
                <th style="width: 13%;">תוקף</th>
                <th>כרטיס ויזואלי</th>
            </tr>
        </thead>
        <tbody>
            {output_table}
        </tbody>
    </table>
</body>
</html>
"""

HTML_ROW_TEMPLATE = """
<tr>
    <td style="text-align: center; background-color: #f8f9fa; font-weight: bold;">{counter}</td>
    <td style="font-weight: 500;">{store}</td>
    <td style="white-space: nowrap;">{order_date}</td>
    <td style="font-weight: 700; color: #0a3847;">{voucher_code}</td>
    <td style="font-weight: 800;">₪{amount}</td>
    <td style="color: #666; font-size: 13px;">{valid_date}</td>
    <td style="padding: 5px;">
        <div style="width: 210px; border: 1.2px solid #0a3847; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; margin: 0 auto; background: white;">
            <div style="padding: 8px 10px; direction: rtl; text-align: right;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; flex-direction: column;">
                        <span style="color: #6d7e8b; font-size: 11px; font-weight: 700;">יתרה עדכנית</span>
                        <div style="font-size: 24px; font-weight: 900; color: #0a3847; line-height: 1;">
                            <span style="font-size: 14px; margin-left: 1px;">₪</span>{amount}
                        </div>
                    </div>
                    <img src="https://cdn.10bis.co.il/voucher-card-vendors/shefa_logo.svg" style="width: 45px; height: auto;">
                </div>
                <div style="font-size: 16px; font-weight: 800; color: #0a3847; text-align: left; direction: ltr; margin-top: 5px;">
                    {voucher_code}
                </div>
            </div>
            <div style="border-top: 1px solid #eee; margin: 0 8px;"></div>
            <div style="padding: 5px; background-color: #fcfcfc; text-align: center; display: flex; justify-content: center;">
                <img src="https://cdn.10bis.co.il/voucher-card-vendors/shefa_logo.svg" style="height: 16px; width: auto; display: block;">
            </div>
        </div>
    </td>
</tr>
"""

def main_procedure():
    # If token exists, use the token to authenticate 10bis
    if os.path.exists(SESSION_PATH) and os.path.exists(TOKEN_PATH):
        session = load_pickle(SESSION_PATH)
        user_token = load_pickle(TOKEN_PATH)
        session.user_token = user_token

    # If there's no token, authenticate 10bis and extract auth tokens
    else:
        session = auth_tenbis()
        if(not session):
            print("exit")
            return
        create_pickle(session, SESSION_PATH)

    rows_data=''
    count = 0
    total_amount = 0
    years_to_check = -abs(input_number('How many years back to scan? ')) * 12
    for num in range(0, years_to_check, -1):
        month_json_result = get_report_for_month(session, str(num))
        for order in month_json_result:
 
            used, voucher_code, amount, valid_date = get_shefa_order_info(session, order['orderId'], order['restaurantId'], order.get('orderDateStr', ''))
            if not used:
                rows_data += HTML_ROW_TEMPLATE.format( 
                    counter=str(count),
                    store=order.get('restaurantName', 'שפע ברכת השם'),
                    order_date=order.get('orderDateStr', 'N/A'),
                    voucher_code=voucher_code,
                    amount=amount,
                    valid_date=valid_date
                    )
                
                count += 1
                total_amount += float(amount)
                print("Token found! ", count, order['orderDateStr'], voucher_code or 'N/A', amount, valid_date or 'N/A')

    if count > 0:
        write_file(OUTPUT_PATH, HTML_PAGE_TEMPLATE.format(output_table=rows_data))
        print(f"{str(count)} tokens were found with total of {total_amount} NIS!")
        print(f'Please find your report here: {CWD} ({FILENAME})')
    else:
        print('No tokens were found.')

def input_number(message):
    while True:
        try:
            userInput = int(input(message))       
        except ValueError:
            print("Not an integer! Try again. (examples: 1,2,3,4,5)")
            continue
        else:
            return userInput 
       

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_pickle(obj, path):
    with open(path, 'wb') as session_file:
        pickle.dump(obj, session_file)

def load_pickle(path):
    with open(path, 'rb') as session_file:
        objfrompickle = pickle.load(session_file)
        return objfrompickle
                
def print_hebrew(heb_txt):
    print(heb_txt[::-1])

def get_report_for_month(session, month):
    endpoint = TENBIS_FQDN + "/NextApi/UserTransactionsReport"
    payload = {"culture": "he-IL", "uiCulture": "he", "dateBias": month}
    headers = {
        "content-type": "application/json",
        "user-token": session.user_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Referer": "https://www.10bis.co.il/"
    }
    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    
    resp_json = json.loads(response.text)
    error_msg = resp_json['Errors']
    success_code = resp_json['Success']
    if(not success_code):
        print_hebrew((error_msg[0]['ErrorDesc']))
        return

    all_orders = resp_json['Data'].get('orderList', [])
   
    sel_orders = []
    for i, order in enumerate(all_orders, start=1):
        if order.get('restaurantId') == RES_ID_SHEFA:
            sel_orders.append(order)
            #print(f"\nOrder #{i}:")
            #for key, value in order.items():
            #    print(f"  {key}: {value}")
            #print(f"Order ID: {order.get('orderId')}, Restaurant ID: {order.get('restaurantId')}")
            
    return sel_orders
    
        
def get_shefa_order_info(session, order_id, res_id, order_date_str=""):
    #print(f"Fetching information for Order ID: {order_id}, Restaurant ID: {res_id}")
    
    endpoint = f"https://api.10bis.co.il/api/v2/VoucherCards?orderId={order_id}"
    
    headers = {
        "content-type": "application/json",
        "user-token": session.user_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Origin": "https://www.10bis.co.il",
        "Referer": f"https://www.10bis.co.il/next/order-summary/{order_id}",
    }    
    
    try:
        response = session.get(endpoint, headers=headers, verify=False)
        if(DEBUG):
            print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        
        if response.status_code != 200:
            print(f"Error: Status Code {response.status_code}")
            print(f"Response: {response.text}")
            return True, '', 0, ''
        
        resp_json = response.json()
        
        balance = resp_json.get('balance', 0)
        used = (balance <= 0)
            
        if not used:
            card_number = resp_json.get('cardNumber', 'N/A')
            amount = balance
            
            raw_expiry = resp_json.get('validDate') or resp_json.get('expiryDate') 
            if not raw_expiry and 'cards' in resp_json and len(resp_json['cards']) > 0: 
                raw_expiry = resp_json['cards'][0].get('expiryDate') 
                
            if raw_expiry: 
                valid_date = str(raw_expiry).split('T')[0] 
                if '-' in valid_date: 
                    y, m, d = valid_date.split('-') 
                    valid_date = f"{d}.{m}.{y}" 
            else: 
                try: 
                    d, m, y = order_date_str.split('.') 
                    year_prefix = "20" if len(y) == 2 else "" 
                    full_year = int(year_prefix + y) 
                    valid_date = f"{d}.{m}.{full_year + 5}" 
                except: 
                    valid_date = "5 שנים מהרכישה"
                
            return used, card_number, amount, valid_date
        
    except Exception as e:
        print(f"Exception occurred: {e}")

    return True, '', 0, ''

def auth_tenbis():
    # Phase one -> Email
    email = input("Enter email: ")
    endpoint = TENBIS_FQDN + "/NextApi/GetUserAuthenticationDataAndSendAuthenticationCodeToUser"

    payload = {"culture": "he-IL", "uiCulture": "he", "email": email}
    headers = {
        "content-type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Referer": "https://www.10bis.co.il/"
    }
    session = requests.session()

    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    
    resp_json = json.loads(response.text)
    error_msg = resp_json['Errors']

    if (200 <= response.status_code <= 210 and (len(error_msg) == 0)):
        print("User exist, next step is...")
    else:
        print("login failed")
        print_hebrew((error_msg[0]['ErrorDesc']))
        return False

    # Phase two -> OTP
    endpoint = TENBIS_FQDN + "/NextApi/GetUserV2"
    auth_token =  resp_json['Data']['codeAuthenticationData']['authenticationToken']
    shop_cart_guid = resp_json['ShoppingCartGuid']

    otp = input("Enter OTP: ")
    payload = {"shoppingCartGuid": shop_cart_guid,
                "culture":"he-IL",
                "uiCulture":"he",
                "email": email,
                "authenticationToken": auth_token,
                "authenticationCode": otp}

    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    resp_json = json.loads(response.text)
    error_msg = resp_json['Errors']
    user_token = resp_json['Data']['userToken']
    if (200 <= response.status_code <= 210 and (len(error_msg) == 0)):
        print("login successful...")
    else:
        print("login failed")
        print_hebrew((error_msg[0]['ErrorDesc']))
        return False

    create_pickle(user_token, TOKEN_PATH)
    session.user_token = user_token

    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        print(session)

    return session

if __name__ == '__main__':
    main_procedure()
