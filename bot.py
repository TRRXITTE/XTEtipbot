import requests
import sqlite3
import threading
import configparser
import argparse
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

# Global variables for SQLite database
DB_FILE = 'user_addresses.db'
CREATE_TABLE_QUERY = '''
CREATE TABLE IF NOT EXISTS user_addresses (
    user_id INTEGER PRIMARY KEY,
    wallet_address TEXT NOT NULL
)
'''

# Global variables for wallet state
wallet_state = None
wallet_lock = threading.Lock()

def initialize_database():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(CREATE_TABLE_QUERY)
    connection.commit()
    connection.close()

# Read configuration from the file
config = configparser.ConfigParser()
config.read('config.ini')

WALLET_API_URL = config['WALLET']['API_URL']
WALLET_API_KEY = config['WALLET']['API_KEY']
TELEGRAM_BOT_TOKEN = config['TELEGRAM']['BOT_TOKEN']

def send_api_request(endpoint, method='GET', payload=None):
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}'}

    if method == 'GET':
        response = requests.get(endpoint, headers=headers)
    elif method == 'POST':
        response = requests.post(endpoint, json=payload, headers=headers)
    else:
        raise ValueError(f'Unsupported HTTP method: {method}')

    return response


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Welcome to the Advanced Tip Bot! Use /help to see available commands.')

    def save_wallet():
    # Implement saving the wallet state
    global wallet_state, wallet_lock

    if wallet_state is not None:
        endpoint = f'{WALLET_API_URL}/save'
        headers = {'Authorization': f'Bearer {WALLET_API_KEY}', 'Content-Type': 'application/json'}
        payload = wallet_state  # You may need to adjust the payload format based on your wallet API

        response = requests.post(endpoint, json=payload, headers=headers)

        if response.status_code == 200:
            print('Wallet saved successfully.')
        else:
            print(f'Error saving wallet: {response.status_code}, {response.text}')

        def auto_save():
    # Implement auto-saving every 1 minute
    threading.Timer(60.0, auto_save).start()
    with wallet_lock:
        save_wallet()


        def register_address(update: Update, context: CallbackContext) -> None:
    # Example usage: /register_address XT2BB8bBWQuSoSJYmWJT4N8xC4nQWGzd5NmoQRrHPRXLCdo1XsyzbZGfXJpgVg3zCNhguuMT9ktpwHSteLXHcTYK1oj1KZpcw
    # Register the user's wallet address in the database
    if len(context.args) == 1:
        user_id = update.message.from_user.id
        wallet_address = context.args[0]

        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        cursor.execute('INSERT OR REPLACE INTO user_addresses (user_id, wallet_address) VALUES (?, ?)', (user_id, wallet_address))
        connection.commit()
        connection.close()

        update.message.reply_text(f'Wallet address {wallet_address} registered for user {user_id}')
    else:
        update.message.reply_text('Usage: /register_address <wallet_address>')


        def get_balance(update: Update, context: CallbackContext) -> None:
    # Example usage: /get_balance XT2BB8bBWQuSoSJYmWJT4N8xC4nQWGzd5NmoQRrHPRXLCdo1XsyzbZGfXJpgVg3zCNhguuMT9ktpwHSteLXHcTYK1oj1KZpcw
    if len(context.args) == 1:
        address = context.args[0]
        balance_info = fetch_balance(address)

        if balance_info:
            reply_text = f'Balance for address {address}:\nUnlocked: {balance_info["unlocked"]}\nLocked: {balance_info["locked"]}'
            update.message.reply_text(reply_text)
        else:
            update.message.reply_text(f'Error fetching balance for address {address}')
    else:
        update.message.reply_text('Usage: /get_balance <wallet_address>')

def fetch_balance(address):
    endpoint = f'{WALLET_API_URL}/balance/{address}'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}'}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return None



def withdraw_funds(update: Update, context: CallbackContext) -> None:
    # Example usage: /withdraw_funds XT2BB8bBWQuSoSJYmWJT4N8xC4nQWGzd5NmoQRrHPRXLCdo1XsyzbZGfXJpgVg3zCNhguuMT9ktpwHSteLXHcTYK1oj1KZpcw 100
    if len(context.args) == 2:
        destination_address = context.args[0]
        amount = int(context.args[1])

        # You may want to add additional validation here, such as checking if the amount is positive

        withdrawal_info = perform_withdrawal(destination_address, amount)

        if withdrawal_info:
            reply_text = f'Withdrawal successful!\nTransaction Hash: {withdrawal_info["transactionHash"]}\nFee: {withdrawal_info["fee"]}\nRelayed to Network: {withdrawal_info["relayedToNetwork"]}'
            update.message.reply_text(reply_text)
        else:
            update.message.reply_text(f'Error withdrawing funds')
    else:
        update.message.reply_text('Usage: /withdraw_funds <destination_address> <amount>')

def perform_withdrawal(destination_address, amount):
    endpoint = f'{WALLET_API_URL}/transactions/send/basic'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}', 'Content-Type': 'application/json'}
    payload = {
        'destination': destination_address,
        'amount': amount
        # You can add additional parameters such as paymentID if needed
    }

    response = requests.post(endpoint, json=payload, headers=headers)

    if response.status_code == 201:
        return response.json()
    else:
        return None


def send_tip(destination, amount, payment_id):
    endpoint = f'{WALLET_API_URL}/transactions/send/basic'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}', 'Content-Type': 'application/json'}
    payload = {
        'destination': destination,
        'amount': amount,
        'paymentID': payment_id
    }

    response = requests.post(endpoint, json=payload, headers=headers)
    tip_response = response.json()

    if response.status_code == 201:
        # Transaction was successful, get additional details
        transaction_details = get_transaction_details(tip_response['transactionHash'])
        tx_key = get_tx_key(tip_response['transactionHash'])

        # Merge transaction key and output details
        tip_response['transactionDetails'] = {
            'transactionHash': tip_response['transactionHash'],
            'txKey': tx_key,
            'details': transaction_details
        }

    return tip_response

def get_transaction_details(transaction_hash):
    endpoint = f'{WALLET_API_URL}/transactions/hash/{transaction_hash}'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}'}

    response = requests.get(endpoint, headers=headers)
    return response.json()

def get_tx_key(transaction_hash):
    endpoint = f'{WALLET_API_URL}/transactions/privatekey/{transaction_hash}'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}'}

    response = requests.get(endpoint, headers=headers)
    return response.json().get('transactionPrivateKey', '')


def get_wallet_status(update: Update, context: CallbackContext) -> None:
    # Implement getting the wallet sync status, peer count, and hashrate
    endpoint = f'{WALLET_API_URL}/status'
    headers = {'Authorization': f'Bearer {WALLET_API_KEY}'}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        status_info = response.json()
        reply_text = (
            f'Wallet Sync Status:\n'
            f'Wallet Block Count: {status_info["walletBlockCount"]}\n'
            f'Local Daemon Block Count: {status_info["localDaemonBlockCount"]}\n'
            f'Network Block Count: {status_info["networkBlockCount"]}\n'
            f'Peer Count: {status_info["peerCount"]}\n'
            f'Hashrate: {status_info["hashrate"]}\n'
            f'Is View Wallet: {status_info["isViewWallet"]}\n'
            f'Sub Wallet Count: {status_info["subWalletCount"]}'
        )
        update.message.reply_text(reply_text)
    else:
        update.message.reply_text(f'Error fetching wallet status: {response.status_code}, {response.text}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Advanced Tip Bot')
    parser.add_argument('--create-wallet', action='store_true', help='Create a new wallet')
    parser.add_argument('--open-wallet', action='store_true', help='Open an existing wallet')
    parser.add_argument('--daemon-host', type=str, help='Daemon host for opening a wallet')
    parser.add_argument('--daemon-port', type=int, help='Daemon port for opening a wallet')
    parser.add_argument('--filename', type=str, help='Wallet filename for opening a wallet')
    parser.add_argument('--password', type=str, help='Wallet password for opening a wallet')

    args = parser.parse_args()

    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    if args.create_wallet:
        create_wallet(None, None)  # You may need to adjust the parameters

    if args.open_wallet:
        open_wallet(None, None, args.daemon_host, args.daemon_port, args.filename, args.password)

    # Add handlers for various commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("open_wallet", open_wallet))
    dp.add_handler(CommandHandler("create_wallet", create_wallet))
    dp.add_handler(CommandHandler("close_wallet", close_wallet))
    dp.add_handler(CommandHandler("get_transactions", get_transactions))
    dp.add_handler(CommandHandler("get_transaction_details", get_transaction_details))
    dp.add_handler(CommandHandler("register_address", register_address))
    dp.add_handler(CommandHandler("get_balance", get_balance))
    dp.add_handler(CommandHandler("get_txkey", get_txkey))
    dp.add_handler(CommandHandler("create_new_address", create_new_address))
    dp.add_handler(CommandHandler("withdraw_funds", withdraw_funds))
    dp.add_handler(CommandHandler("save_wallet", save_wallet))
    dp.add_handler(CommandHandler("get_wallet_status", get_wallet_status))

    auto_save()  # Start the auto-save thread

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
