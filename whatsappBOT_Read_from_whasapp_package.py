import json
import re
import time
import copy
import selenium.common.exceptions as ex
from selenium import webdriver
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from dataclasses import dataclass
from typing import Callable, Any, Self


@dataclass
class GroupMessage:
    id: str
    group: str
    sender: str
    text: str | None
    time: str


@dataclass
class GroupMessageHandler:
    """A handler for messages from a given group.

    A `GroupMessageHandler` instance specifies which new messages of
    a group should be passed to a given callback function.

    Note that an instance of this class is merely a descriptor; on its own,
    it doesn't do anything. You'd need to pass it to the `add_handler` method
    of a `WhatsAppGroupBot` to actually handle messages.

    Attributes:
        callback: A function that receives a new matching group
            message and an instance of a running bot.
        group: The name of the group to associate this handler with.
            The callback will only receive new messages from this group.
        senders: A list of the phone numbers of group members whose messages
            should be passed to the callback. This attribute acts as a filter
            for the group messages. Setting this to `None` (the default value)
            implies that the callback should receive messages from all group
            members.
    """

    # TODO: type the 'Any' as WhatsAppGroupBot (low priority)
    callback: Callable[[GroupMessage, Any], Any]
    group: str
    senders: list[str] | None = None


def without_stacktrace(exception: BaseException | None):
    """Return a copy of a WebDriverException, but without the cryptic stacktrace.

    If the given exception is not a WebDriverException, return the exception as is.

    This function is really only useful when printing errors. By default, printing
    a WebDriverException outputs a long, cryptic stacktrace that clutters the console
    (and thus makes debugging a bit difficult). See also the `print_error` function.
    """

    if isinstance(exception, ex.WebDriverException):
        e = copy.copy(exception)
        e.stacktrace = None

        # Recursively remove stacktrace from cause and context exceptions.
        # See https://stackoverflow.com/q/24752395
        # TODO: is this necessary? (If you do this, then know that you'll
        # do it for any exception, not just a WebDriverException)
        # e.__cause__ = without_stacktrace(exception.__cause__)
        # e.__context__ = without_stacktrace(exception.__context__)

        return e.with_traceback(exception.__traceback__)

    return exception


def print_error(msg, exception: BaseException):
    print(msg, without_stacktrace(exception))


class WhatsAppGroupBot:
    """A bot for sending and receiving group messages from WhatsApp Web.

    Example:
        You'd typically use this class in the following manner:

        ```
        bot = WhatsAppGroupBot()

        # Send a message to given group
        bot.send_message(group='IHS NOR HUA', text='Hello there!')

        # Define a callback to be called whenever a new group message is received
        def callback(message, bot):
            print('New message received', message)
        bot.add_handler(group='IHS NOR HUA', callback=callback)

        # Run a loop to trigger the callback whenever new messages arrive.
        bot.run_loop()
        ```
    """

    def __init__(self):
        self._handlers: list[GroupMessageHandler] = []
        self._current_group = None

        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--accept-lang=en-us")
        chrome_options.add_argument("--disable-notifications")

        self._driver = webdriver.Chrome(options=chrome_options)
        self._driver.implicitly_wait(4)
        self._driver.get("https://web.whatsapp.com")

        self._LAST_MESSAGE_DATA_ID_LOGFILE_PATH = "./last-message-data-ids.json"
        self._DATA_ID_PATTERN = re.compile(r"^.+@.+_(?P<sender>\d+)@.+$")
        # The pre_plain_text looks like: "[9:49 AM, 4/28/2023] Boss Moses: "
        self._PRE_PLAIN_TEXT_PATTERN = re.compile(r"^\[(?P<time>.+)\].+$")

    def add_handler(self, handler: GroupMessageHandler):
        """Register a handler for new messages.

        The handler's callback will be called with each new message
        matching the group and senders specified on the handler.
        """
        if handler not in self._handlers:
            self._handlers.append(handler)

    def remove_all_handlers(self):
        """Remove all the handlers registered on the bot.

        One situation you'd need this is when you're creating handlers dynamically,
        and you want to reset and register handlers on every iteration of the
        `run_loop()`. See `run_loop()` for more info.
        """
        self._handlers.clear()

    def send_message(self, group: str, text: str):
        """Send a text message to given group."""
        self._open_group_chat(group)

        # Locate the chat box
        chat_box = self._driver.find_element(By.XPATH, '//div[@title="Type a message"]')

        # Input your desired text message
        for line in text.splitlines():
            chat_box.send_keys(line.strip())
            chat_box.send_keys(Keys.CONTROL + Keys.ENTER)

        # Send the message
        chat_box.send_keys(Keys.ENTER)

    def run_loop(self, before_each: Callable[[Self], Any] | None = None, interval=10):
        """Start an infinite 'event loop' to retrieve messages from groups.

        Because this starts an infinite loop, you'd want to call it at the end of your
        program.

        Args:
            before_each: Optional. A function to run at the start of every iteration
                of the loop. The function will be called with the bot instance, so
                you can use this to, for example, reset or register handlers on the
                bot on each iteration.
            interval: Optional. The amount of seconds to wait between iterations.
                Defaults to 10.

        Example:
            Start the event loop and, on each iteration, get new group infos from OWS,
            then reset the handlers and attach new handlers based on the group infos:
            ```
            def before_each(bot):
                bot.remove_all_handlers()
                group_contacts = get_groups_and_contacts()
                for group in group_contacts:
                    contact_nums = group_contacts[group].keys()
                    handler = GroupMessageHandler(
                        group=group,
                        senders=contact_nums,
                        callback=callback
                    )
                    bot.add_handler(handler)

            bot.run_loop(before_each)
            ```
        """

        # TODO: prevent running multiple loops?
        # TODO: allow stopping a running loop?

        while True:
            if before_each:
                before_each(self)
            groups_to_watch = {handler.group for handler in self._handlers}
            for group in groups_to_watch:
                try:
                    messages = self._get_unread_messages(group)
                except Exception as e:
                    print_error(f"Failed to get unread messages from {group}\n", e)
                    continue

                for message in messages:
                    self._call_matching_handlers(message)
                    # TODO: what if a handler throws? Should you still mark the message as read or not?
                    self._set_last_read_message_id(message.id)
            time.sleep(interval)

    def _get_unread_messages(self, group: str):
        try:
            self._open_group_chat(group)
        except Exception as e:
            raise Exception(f"Can't find group {group}.") from e

        new_messages: list[GroupMessage] = []

        unread_message_rows = self._get_unread_message_rows_from_current_group()
        for row in unread_message_rows:
            try:
                message = self._get_message_from_row(row)
            except Exception as e:
                print_error("Error parsing message row\n", e)
                continue

            new_messages.append(message)

        return new_messages

    def _call_matching_handlers(self, message: GroupMessage):
        for handler in self._handlers:
            if message.group == handler.group and (
                handler.senders is None or message.sender in handler.senders
            ):
                handler.callback(message, self)

    def _open_group_chat(self, group: str):
        search_box = WebDriverWait(self._driver, 120).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[title="Search input textbox"]')
            )
        )

        # Clear the search box as it may contain text from previous iteration
        search_box.send_keys(Keys.CONTROL + "a")
        search_box.send_keys(Keys.DELETE)
        search_box.send_keys(group)

        group_chat = self._driver.find_element(
            By.CSS_SELECTOR, f'#pane-side span[title="{group}"]'
        )
        group_chat.click()
        self._current_group = group

    def _get_unread_message_rows_from_current_group(self):
        self._assert_group_is_open()
        last_read_data_id = self._scroll_until_last_read_message_found()
        if last_read_data_id:
            unread_message_row_selector = f"[role='row']:has(> [data-id='{last_read_data_id}']) ~ [role='row'] > [data-id^='false_']"
        else:
            unread_message_row_selector = f"[role='row'] > [data-id^='false_']"

        # Find every incoming message row that's after the last row recorded
        unread_message_rows = self._driver.find_elements(
            By.CSS_SELECTOR, unread_message_row_selector
        )

        return unread_message_rows

    def _assert_group_is_open(self):
        """Assert that there's an open group chat.

        NOTE: This function is just for debugging. Call it in any method
        that requires a group to already be open. If this function ever
        raises an exception (it shouldn't), then it means there's a bug
        in this bot code.
        """
        assert (
            self._current_group
        ), "No open group. Did you forget to call _open_group_chat()?"

    def _get_last_read_message_id(self):
        self._assert_group_is_open()
        try:
            with open(
                self._LAST_MESSAGE_DATA_ID_LOGFILE_PATH, "r", encoding="utf-8"
            ) as logfile:
                last_data_ids = json.load(logfile)
        except FileNotFoundError:
            last_data_ids = {}
        last_data_id = last_data_ids.get(self._current_group, None)
        return last_data_id

    def _set_last_read_message_id(self, data_id: str):
        self._assert_group_is_open()
        try:
            with open(
                self._LAST_MESSAGE_DATA_ID_LOGFILE_PATH, "r", encoding="utf-8"
            ) as logfile:
                last_data_ids = json.load(logfile)
        except FileNotFoundError:
            last_data_ids = {}

        last_data_ids[self._current_group] = data_id

        with open(
            self._LAST_MESSAGE_DATA_ID_LOGFILE_PATH, "w", encoding="utf-8"
        ) as logfile:
            json.dump(last_data_ids, logfile)

    def _scroll_until_last_read_message_found(self):
        """Scroll up until the last read message in the open group is found.

        WhatsApp Web lazy loads messages, so Selenium may not find the last read
        message row, if the message hasn't already been loaded. Repeatedly scrolling
        up triggers WhatsApp Web to load as many messages as there are until the
        target message is found. (At the end, this function scrolls back down.)

        Returns the data id of the last read message, if the message is found.
        If the message isn't found, returns `None`.
        """

        self._assert_group_is_open()

        conversation_panel = self._driver.find_element(
            By.CSS_SELECTOR, "[data-testid='conversation-panel-messages']"
        )

        last_message_row_found = False
        last_read_data_id = self._get_last_read_message_id()

        while True:
            # Use find_elements not find_element to avoid exceptions
            last_message_row_found = last_read_data_id and self._driver.find_elements(
                By.CSS_SELECTOR, f"[data-id='{last_read_data_id}']"
            )
            if last_message_row_found:
                break

            chat_top_reached = self._driver.find_elements(
                By.XPATH,
                "//*[@data-testid='msg-notification-container']//*[contains (text(), 'Messages are end-to-end encrypted')]",
            )
            if chat_top_reached:
                break

            conversation_panel.send_keys(Keys.HOME)

        # Scroll all the way back down
        conversation_panel.send_keys(Keys.END)

        return last_read_data_id if last_message_row_found else None

    def _get_message_from_row(self, row: WebElement):
        """Parse a message row into a GroupMessage object."""

        data_id = row.get_dom_attribute("data-id")
        data_id_match = self._DATA_ID_PATTERN.search(data_id)
        sender = "+" + data_id_match.group("sender")

        # NOTE: [data-pre-plain-text] is present wherever there's text.

        message_container = row.find_element(By.CSS_SELECTOR, "[data-pre-plain-text]")
        pre_plain_text = message_container.get_dom_attribute("data-pre-plain-text")
        pre_plain_text_match = self._PRE_PLAIN_TEXT_PATTERN.search(pre_plain_text)
        raw_time = pre_plain_text_match.group("time")
        formatted_time = self._format_message_time(raw_time)
        message_text_container = message_container.find_element(
            By.CLASS_NAME, "selectable-text"
        )
        text = message_text_container.text

        # Temporary workaround to avoid empty messages on OWS
        # Empty messages can come from emojis, for example,
        # because WhatsApp renders emojis as <img>s not text
        if text == "":
            raise Exception("Empty message text (emojis maybe?)")

        # TODO: what if the message is "Waiting for message..."?

        message = GroupMessage(
            id=data_id,
            group=self._current_group,
            sender=sender,
            text=text,
            time=formatted_time,
        )

        return message

    def _format_message_time(self, time: str):
        time_formats = [
            "%I:%M %p, %m/%d/%Y",  # 12-hour format with AM/PM
            "%H:%M:%S, %m/%d/%Y",  # 24-hour format with seconds
            "%H:%M, %m/%d/%Y",  # 24-hour format without seconds
            "%I:%M:%S %p, %m/%d/%Y",  # 12-hour format with seconds and AM/PM
            "%I:%M %p, %d/%m/%Y",  # 12-hour format with AM/PM (day/month/year)
            "%H:%M:%S, %d/%m/%Y",  # 24-hour format with seconds (day/month/year)
            "%H:%M, %d/%m/%Y",  # 24-hour format without seconds (day/month/year)
            "%I:%M:%S %p, %d/%m/%Y",  # 12-hour format with seconds and AM/PM (day/month/year)
            "%Y-%m-%d %H:%M:%S",  # ISO format without milliseconds
            "%Y-%m-%d %H:%M:%S.%f",  # ISO format with milliseconds
            "%Y-%m-%d %I:%M:%S %p",  # 12-hour ISO-like format without milliseconds
        ]
        for format_str in time_formats:
            try:
                datetime_obj = datetime.strptime(time, format_str)
                formatted_time = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                return formatted_time
            except ValueError:
                continue

        # If no valid format is found
        raise ValueError("Invalid time format: {}".format(time))
