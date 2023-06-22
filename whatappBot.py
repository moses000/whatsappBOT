import requests
import re
from dataclasses import dataclass
from selenium import webdriver
import selenium.common.exceptions as ex
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from tkinter import *
import time
import getpass


COMMON_HEADERS = {"Content-type": "application/x-www-form-urlencoded"}

# This is just to store the IDs of group infos recorded
# It seems there's no need to store this in a file instead
# because whenever this script is restarted, OWS sends just
# the unrecorded ones.
RECORDED_GROUP_INFO_IDS = set()

def get_auth():
    owsUserName = ""
    owsPassword = ""
    return owsUserName, owsPassword

def send_OWS_request(service_url, data, auth=get_auth()):
# def send_OWS_request(service_url, data):
    response = requests.post(
        service_url,
        verify=False,
        auth=auth,
        headers=COMMON_HEADERS,
        data=data,
        timeout=None,
    )
    # print(response.raise_for_status())
    response.raise_for_status()
    response_data = response.json()
    print("THis is ates>>>>>>"+str(response_data))
    return response_data

def get_group_infos():
    service_url = ""
    
    try:
        print("+++>>>+++")
        response_data = send_OWS_request(service_url, data=[])
        
        # print(response_data)
        
        group_infos = response_data["results"]
        
        print(">>>>>>"+str(group_infos))
    
    except Exception as e:
        print (e)

        # print(group_infos)
        # print(response_data)
        
        # Let the outermost try catch it.
        raise
    return group_infos


def init_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--accept-lang=en-us")
    chrome_options.add_argument("--disable-notifications")
    # prefs = {"download.default_directory": r"D:\SA IHS BOT\Mail Download"}
    # chrome_options.add_experimental_option("prefs", prefs)

    # driver = webdriver.Chrome("D:\\SA IHS BOT\\chromedriver.exe", options=chrome_options)
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(60)
    return driver


def open_group_chat(group):
    search_box = driver.find_element(By.CSS_SELECTOR, '[title="Search input textbox"]')

    # Clear the search box as it may contain text from a previous search
    search_box.send_keys(Keys.CONTROL + "a")
    search_box.send_keys(Keys.DELETE)
    search_box.send_keys(group)

    group_chat = driver.find_element(By.CSS_SELECTOR, f'#pane-side [title="{group}"]')

    group_chat.click()


def send_message_to_group(group, message):
    open_group_chat(group)

    # Locate the chat box
    chat_box = driver.find_element(By.XPATH, '//div[@title="Type a message"]')

    # Input your desired text message
    for line in message.splitlines():
        chat_box.send_keys(line.strip())
        chat_box.send_keys(Keys.CONTROL + Keys.ENTER)

    # Send the message
    chat_box.send_keys(Keys.ENTER)


def filter_monitor_group_infos(monitor_groups, group_infos):
    filtered = []
    
    for group_info in group_infos:
        monitor_group = next((group for group in monitor_groups if group_info["sbc"] in group), None)
        if group_info["id"] not in RECORDED_GROUP_INFO_IDS and monitor_group:
            group_info = group_info.copy()
            group_info['monitor_group'] = monitor_group
            filtered.append(group_info)
    return filtered

def verify_credentials(username, password):
    try:
        # TODO: this doesn't work yet
        service_url = ""
        response_data = send_OWS_request(
            service_url, data=None, auth=(username, password)
            # service_url, data=None
        )
        return response_data["results"] == "Login Successful"
    except:
        # raise Exception("Failed to verify credentials")
        return True


def handle_submit():
    global driver, username, password, monitorGrp, region_name
    username = nameE.get()
    password = pwordE.get()
    monitorGrp = monitorE.get()
    region_name = regionE.get()

    if not verify_credentials(username, password):
        raise Exception("Incorrect username or password")

    root.destroy()

    driver = init_webdriver()
    driver.get("https://web.whatsapp.com")
    print("Please scan the barcode")

    monitor_groups = [group.strip() for group in monitorGrp.split(",")]

    while True:
        try:
            group_infos = get_group_infos()
            print(group_infos)
            if not group_infos:
                print("Warning: No group infos configured")

            filtered_group_infos = filter_monitor_group_infos(
                monitor_groups, group_infos
            )
            print("filtered_group_infos>>>>>>"+str(filtered_group_infos))
            if not filtered_group_infos:
                print("Warning: No groups you entered match those returned ")

            for group_info in filtered_group_infos:
                send_message_to_group(
                    group=group_info["monitor_group"],
                    message=group_info["context"],
                )
                RECORDED_GROUP_INFO_IDS.add(group_info["id"])
        except Exception as e:
            print(e)
        time.sleep(5)


if __name__ == "__main__":
    root = Tk()
    root.title("WHATSAPP BOT")
    root.configure(background="white")
    user = getpass.getuser()
    # try:
    #     root.iconbitmap(f'''C:\\AIRTEL BOT\\BOT_ICO.ico''')
    # except Exception as e:
    #     print('Cannot find BOT_ICO.ico '+ str(e))
    width = 450
    height = 350
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width / 2) - (width / 2)
    y = (screen_height / 2) - (height / 2)
    root.geometry("%dx%d+%d+%d" % (width, height, x, y))
    root.resizable(0, 0)

    PASSWORD = StringVar()
    USERNAME = StringVar()
    REPORT = StringVar()
    REGION = StringVar()

    # ==============================FRAMES=========================================
    Top = Frame(root, bd=2, relief=RIDGE)

    Top.pack(side=TOP, fill=X)
    Form = Frame(root, height=300, background="white")
    Form.pack(side=TOP, pady=20)

    # ==============================LABELS=========================================
    lbl_title = Label(
        Top,
        text="Login with OWS Account & Password",
        font=("calibri", 12),
        background="#DEB887",
    )
    lbl_title.pack(fill=X)
    lbl_username = Label(
        Form, text="User Account:", font=("calibri", 10), bd=10, background="white"
    )
    lbl_username.grid(row=1, column=0)
    lbl_password = Label(
        Form, text="Password:", font=("calibri", 10), bd=10, background="white"
    )
    lbl_password.grid(row=2, column=0)
    lbl_monitor = Label(
        Form, text="WhatsApp Group:", font=("calibri", 10), bd=10, background="white"
    )
    lbl_monitor.grid(row=3, column=0)
    lbl_group = Label(
        Form, text="Region:", font=("calibri", 10), bd=10, background="white"
    )
    lbl_group.grid(row=4, column=0)
    lbl_text = Label(Form)
    lbl_text.grid(row=5, columnspan=2)

    # ==============================ENTRY WIDGETS==================================
    nameE = Entry(Form, textvariable=USERNAME, font=("Calibri 16"))
    nameE.grid(row=1, column=1)
    nameE.focus()
    pwordE = Entry(Form, textvariable=PASSWORD, show=".", font=("Calibri 16"))
    pwordE.grid(row=2, column=1)
    monitorE = Entry(Form, textvariable=REPORT, font=("Calibri 16"))
    monitorE.grid(row=3, column=1)
    regionE = Entry(Form, textvariable=REGION, font=("Calibri 16"))
    regionE.grid(row=4, column=1)

    # ==============================BUTTON WIDGETS=================================
    btn_login = Button(
        Form,
        text="Login",
        width=15,
        bg="#ff6262",
        font=("calibri", 12),
        command=handle_submit,
    )
    btn_login.grid(pady=25, row=7, columnspan=2)
    btn_login.bind("<Return>", "")

    root.mainloop()

