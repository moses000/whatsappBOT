from whatsappbot import WhatsAppGroupBot, GroupMessage, GroupMessageHandler
from datetime import datetime
import requests
import json
import re

COMMON_HEADERS = {"Content-type": "application/x-www-form-urlencoded"}


def get_auth():
    with open("", "r") as credentials:
        details = credentials.readlines()
        WSusername, WSpassword = details[0].strip(), details[1].strip()
    return WSusername, WSpassword


def send_OWS_request(service_url, data):
    response = requests.post(
        service_url,
        verify=False,
        auth=get_auth(),
        headers=COMMON_HEADERS,
        data=data,
        timeout=None,
    )

    response.raise_for_status()
    response_data = response.json()
    return response_data


def get_groups_and_contacts():
    serviceURL = ""
    data = {"start": 0, "limit": 20}

    response_data = send_OWS_request(serviceURL, data=data)

    group_contacts: dict[str, dict[str, str]] = {}

    contact_pattern = re.compile(r"^(?P<name>.+?)?\s*(?P<num>\+.+?)$")

    for result in response_data["results"]:
        group = result["whatsapp_group"].strip()
        raw_contacts = result["whatsapp_contact"].split(",")
        contacts = {}
        for raw_contact in raw_contacts:
            contact_match = contact_pattern.search(raw_contact)
            raw_name = contact_match.group("name")
            name = raw_name.strip() if raw_name else ""  # None?
            num = contact_match.group("num").replace(" ", "")
            contacts[num] = name
        group_contacts[group] = contacts

    return group_contacts


def before_each(bot: WhatsAppGroupBot):
    global group_contacts

    bot.remove_all_handlers()

    group_contacts = get_groups_and_contacts()
    print(group_contacts)

    if not group_contacts:
        print("Warning: No groups and contacts configured in OWS")

    for group in group_contacts:
        contact_nums = group_contacts[group].keys()
        bot.add_handler(
            GroupMessageHandler(
                group=group, senders=contact_nums, callback=message_callback
            )
        )


def record_message(message: GroupMessage):
    url = ""

    sender_name = group_contacts[message.group][message.sender]
    contact = (sender_name + " " + message.sender).strip()

    data = {
        "whatsapp_contact": contact,
        "whatsapp_group": message.group,
        "whatsapp_message": message.text,
        "message_time": message.time,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image_url": None,
    }
    print("Sending payload:")
    print(json.dumps(data, indent=2))
    print("===")

    send_OWS_request(url, data=data)

    # Record locally only after sending succesfully to OWS
    # with open(LAST_MESSAGE_DATA_ID_LOGFILE_PATH, "r", encoding="utf-8") as logfile:
    #     last_data_ids = json.load(logfile)

    # last_data_ids[message.group] = message.data_id

    # with open(LAST_MESSAGE_DATA_ID_LOGFILE_PATH, "w", encoding="utf-8") as logfile:
    #     json.dump(last_data_ids, logfile)


def message_callback(message: GroupMessage, bot: WhatsAppGroupBot):
    try:
        record_message(message)
    except Exception as e:
        print("Failed to save message to OWS")
        print("Message", message)
        print("Error", e)


if __name__ == "__main__":
    bot = WhatsAppGroupBot()
    group_contacts = None
    bot.run_loop(before_each)
