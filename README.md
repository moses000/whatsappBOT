
# WhatsApp Bot

This is a simple WhatsApp bot that uses Selenium to send messages to WhatsApp groups. It is designed to be used with the web version of WhatsApp.

## Installation

1. Clone the repository:

   ```bash
   git clone (https://github.com/moses000/whatsappBOT.git)
   ```

2. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Install the Chrome WebDriver:

   Download the appropriate Chrome WebDriver for your operating system from [ChromeDriver Downloads](https://sites.google.com/a/chromium.org/chromedriver/downloads) and place it in the project directory.

## Usage

1. Run the bot:

   ```bash
   python whatsapp_bot.py
   ```

2. Enter your WhatsApp username, password, monitor group, and region when prompted.
3. Scan the QR code displayed on the browser to log in to WhatsApp Web.
4. The bot will start sending messages to the specified monitor group based on the group information retrieved from the OWS service.

## Configuration

You can configure the bot by editing the `whatsapp_bot.py` file. You can change the OWS service URL, the search query, and the message to be sent.

## Disclaimer

This bot is for educational purposes only. Use it responsibly and do not spam groups or violate WhatsApp's terms of service.
