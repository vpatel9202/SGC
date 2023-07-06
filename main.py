"""
main.py
Created on: Jul 2, 2023
Author: vpatel9202, Assisted by: OpenAI Chatbot

This is the main entry point for the Google Contacts syncing script.
It utilizes functions defined in other modules to authenticate with the Google People API,
and to sync the contacts between the two accounts.
"""

import os
import configparser
import logging
import shutil
import sys
from logging.handlers import TimedRotatingFileHandler
from datetime import date
from google_auth_oauthlib.flow import InstalledAppFlow

# Constants
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(ROOT_DIR, "settings.conf")
SCOPES = ['https://www.googleapis.com/auth/contacts']
LOG_DIR = os.path.join(ROOT_DIR, "logs")
LOG_LEVEL = 'DEBUG'
LOG_FILE = f"{LOG_DIR}/{date.today():%Y-%m-%d}.log"

# Global Logger
LOGGER = logging.getLogger()


def setup_logger():
    """Configures the logger with handlers for both console and file output."""
    LOGGER.info(f"Setting up logger...")
    if not os.path.isdir(LOG_DIR):
        LOGGER.warning(f"Specified directory '{LOG_DIR}' does not exist so it will be created automatically.")
        os.mkdir(LOG_DIR)

    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=30)
    console_handler = logging.StreamHandler()

    file_handler.setLevel(logging.INFO)
    console_handler.setLevel(logging.WARNING)

    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(filename)s - %(funcName)s (%(lineno)d): %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    LOGGER.setLevel(LOG_LEVEL)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(console_handler)
    LOGGER.info(f"Logger has been successfully setup")


def on_first_run():
    """Check if settings file exists, and if not, copy the template file."""
    TEMPLATE_FILE = os.path.join(ROOT_DIR, "settings.conf.template")
    if not os.path.exists(SETTINGS_FILE):
        LOGGER.warning(f"Settings file not found. Copying template file {TEMPLATE_FILE} to {SETTINGS_FILE}")
        shutil.copy(TEMPLATE_FILE, SETTINGS_FILE)
        LOGGER.info(f"Copied template settings file to {SETTINGS_FILE}")
        LOGGER.warning(f"Please place your Google API credentials in the newly created settings file at {SETTINGS_FILE}")
        sys.exit()
    else:
        LOGGER.info(f"Settings file {SETTINGS_FILE} exists, no need to copy from template.")


def read_config(config_path):
    """Reads configuration from a file."""
    LOGGER.info(f"Reading configuration from file: {config_path}")
    config = configparser.ConfigParser()
    config.read(config_path)
    LOGGER.info(f"Finished reading configuration from file: {config_path}")
    return config


def get_refresh_token(client_id, client_secret, account_name):
    """Initiates OAuth 2.0 flow and returns a refresh token."""
    try:
        print(f"Log in with your {account_name} Google account.")
        LOGGER.info(f"Starting OAuth 2.0 flow for {account_name} Google account...")
        flow = InstalledAppFlow.from_client_config(
            {"installed":
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "access_type": "offline"
                }
            },
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        LOGGER.info(f"Refresh token successfully generated for {account_name} account.")
        return creds.refresh_token
    except Exception as e:
        LOGGER.error(f"Error occurred while generating refresh token for {account_name} account: {e}")


def write_credentials(filename, config):
    """Writes the credentials to a file."""
    try:
        LOGGER.info(f"Writing credentials to file: {filename}")
        with open(filename, 'w') as f:
            config.write(f)
        LOGGER.info('New refresh tokens successfully written to settings.conf')
    except Exception as e:
        LOGGER.error(f"Error occurred while writing credentials to file: {filename}, error: {e}")


def refresh_token_exists(account, config):
    """Check if refresh token is present for a particular account in settings.conf"""
    LOGGER.info(f"Checking if refresh token exists for {account}")
    refresh_token = config.get(account, 'refresh_token', fallback="")
    exists = refresh_token != ""
    if exists:
        LOGGER.info(f"Refresh token for {account} exists.")
    else:
        LOGGER.warning(f"Refresh token for {account} does not exist.")
    return exists

def ensure_refresh_token(account, config):
    """Ensure a refresh token exists for a particular account, generating one if necessary."""
    LOGGER.info(f"Ensuring refresh token for {account}")
    if not refresh_token_exists(account, config):
        generate_and_save_refresh_token(account, config)

def generate_and_save_refresh_token(account, config):
    """Generate a new refresh token and save it to the settings file."""
    LOGGER.info(f"Generating new refresh token for {account}...")
    client_id = config.get(account, 'client_id')
    client_secret = config.get(account, 'client_secret')
    refresh_token = get_refresh_token(client_id, client_secret, account)
    config[account]['refresh_token'] = refresh_token
    write_credentials(SETTINGS_FILE, config)


def main():
    setup_logger()
    on_first_run()
    LOGGER.info("Starting main execution...")
    config = read_config(SETTINGS_FILE)
    ensure_refresh_token('Account1', config)
    ensure_refresh_token('Account2', config)
    LOGGER.info("Main execution finished successfully")


if __name__ == "__main__":
    main()
