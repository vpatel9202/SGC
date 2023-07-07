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
import json
import logging
import shutil
import sys
from logging.handlers import TimedRotatingFileHandler
from datetime import date
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Constants
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(ROOT_DIR, "settings.conf")
DATA_DIR = os.path.join(ROOT_DIR, "data")
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


def get_credentials(account, config):
    """Get valid credentials for the account."""
    creds = None
    client_id = config.get(account, 'client_id')
    client_secret = config.get(account, 'client_secret')
    refresh_token = config.get(account, 'refresh_token')

    creds = Credentials.from_authorized_user_info(
        {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token},
        SCOPES
    )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            LOGGER.info(f"Refreshing expired credentials for {account}...")
            creds.refresh(Request())
        else:
            LOGGER.error(f"Unable to get valid credentials for {account}. Please check your settings.")
            sys.exit(1)
    return creds


def get_people_service(creds):
    """Get a service that communicates to a Google API."""
    return build('people', 'v1', credentials=creds)


def get_all_contacts(account, config):
    """Gets all contact data for a particular account."""

    creds = get_credentials(account, config)
    people_service = get_people_service(creds)

    resource_names = []
    page_token = None
    sync_token = config[account]['contactsSyncToken'] or None
    personFields = 'addresses,ageRanges,biographies,birthdays,braggingRights,coverPhotos,emailAddresses,events,genders,imClients,interests,locales,memberships,metadata,names,nicknames,occupations,organizations,phoneNumbers,photos,relations,relationshipInterests,relationshipStatuses,residences,sipAddresses,skills,taglines,urls,userDefined'

    while True:
        results = people_service.people().connections().list(
            resourceName='people/me',
            pageSize=2000,
            pageToken=page_token,
            personFields=personFields,
            requestSyncToken=True,
            sortOrder='LAST_MODIFIED_DESCENDING',
            sources=['READ_SOURCE_TYPE_CONTACT'],
            syncToken=sync_token,
            prettyPrint=True).execute()

        save_to_file('raw_contacts', account, results)  # Save raw JSON response
        config[account]['contactsSyncToken'] = results.get('nextSyncToken')
        LOGGER.info(f"Obtained nextSyncToken: {config[account]['contactsSyncToken']}, saving to config.")
        write_credentials(SETTINGS_FILE, config)

        connections = results.get('connections', [])
        resource_names.extend([c['resourceName'] for c in connections])

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    contacts = []
    chunked_resource_names = [resource_names[i:i + 200] for i in range(0, len(resource_names), 200)]

    for chunk in chunked_resource_names:
        batch_get_results = people_service.people().getBatchGet(
            resourceNames=chunk,
            personFields=personFields
        ).execute()
        contacts.extend([person['person'] for person in batch_get_results.get('responses', []) if 'person' in person])

    return contacts


def get_group_list(account, config):
    """Gets all contact group data for a particular account."""
    creds = get_credentials(account, config)
    people_service = get_people_service(creds)

    page_token = None
    sync_token = config[account]['groupSyncToken'] or None
    groupFields = 'clientData,groupType,memberCount,metadata,name'

    # Get all contact groups
    results = people_service.contactGroups().list(
        pageSize=1000,
        pageToken=page_token,
        groupFields=groupFields,
        syncToken=sync_token,
        prettyPrint=True).execute()

    save_to_file('raw_groups', account, results)  # Save raw JSON response
    config[account]['groupSyncToken'] = results.get('nextSyncToken')
    LOGGER.info(f"Obtained nextSyncToken: {config[account]['groupSyncToken']}, saving to config.")
    write_credentials(SETTINGS_FILE, config)

    groups = results.get('contactGroups', [])

    return groups


def save_to_file(data_type, account, data):
    """Save the data to a JSON file."""

    if not os.path.isdir(DATA_DIR):
        LOGGER.warning(f"Specified directory '{DATA_DIR}' does not exist so it will be created automatically.")
        os.mkdir(DATA_DIR)

    file_name_base = f"{date.today():%Y-%m-%d}.{account}_{data_type}"
    json_file_path = os.path.join(DATA_DIR, f"{file_name_base}.json")

    with open(json_file_path, 'w') as f:
        json.dump(data, f)


def main():
    LOGGER.info("Starting main execution...")

    setup_logger()
    on_first_run()

    config = read_config(SETTINGS_FILE)
    ensure_refresh_token('Account1', config)
    ensure_refresh_token('Account2', config)

    # Fetch and save contacts
    for account in ['Account1', 'Account2']:
        contacts = get_all_contacts(account, config)
        save_to_file('contacts', account, contacts)

        groups = get_group_list(account, config)
        save_to_file('groups', account, groups)

    LOGGER.info("Main execution finished successfully")


if __name__ == "__main__":
    main()
