#!/usr/bin/python3
import beepy
import datetime
import glob
import logging
# import nmcli
import os
import os.path
import requests
import shutil
import subprocess
import time
import traceback
import urllib.parse
from bs4 import BeautifulSoup


#all SD cards should be configured with ssid "ez Share X100S", where 'X100S' is variable and 
#identifies your camera; this string will be replicated in the album names
#all SD cards should be configured with the same password:
_PASSWORD = "88888888"


#temporary workspace while downloaden/uploading files
_DESTINATION = "./sdcard-sync"
os.makedirs(_DESTINATION, exist_ok=True)


logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d %(funcName)s] %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=logging.DEBUG)

def main_nowifi():
    filenames = get_list_of_filenames_on_card()
    for (directory, filename) in filenames:
        print(directory,filename)
        download( directory, filename)


def main():

    try:

        home_network = find_active_connection()

        #endless polling loop
        while True: 

            ez_ssid = find_first_active_ezshare_ssid()

            if ez_ssid:

                beepy.beep(sound="success")

                try:

                    #import pdb; pdb.set_trace()

                            
                    home_network = find_active_connection()
                    connect_to_ezshare_ssid(ez_ssid)
                    filenames = get_list_of_filenames_on_card()
                    
                    for (directory, filename) in filenames:
                            download_result = download(directory, filename)
                            
                            if download_result:
                                beepy.beep(sound="ping")
                            else:
                                beepy.beep(sound="error")

                    connect_to_home_network(home_network)
                    beepy.beep(sound="ready")

                    logging.debug("Sleeping")
                    time.sleep(10)  # wait an extra 10 seconds before polling again

                except Exception as e:

                    if home_network:
                        connect_to_home_network(home_network)
                    logging.error(f"There's a problem processing '{ez_ssid}': {e}")

            logging.debug("Sleeping")
            time.sleep(10)  # poll every 10 seconds for active cards
                

    #execute this code if CTRL + C is used to kill python script
    except KeyboardInterrupt:

        if home_network:
            connect_to_home_network(home_network)
        print("Bye!")

    except Exception as e:

        if home_network:
            connect_to_home_network(home_network)
        logging.error(traceback.format_exc())
        # Logs the error appropriately.


def find_active_connection():
    connections = nmcli.connection()
    for connection in connections:
        if connection.device != "--":
            logging.info(f"'{connection.name}' is the current network connection")
            return connection.name
    else:
        logging.error("There seems to be no active network connection!")


def find_first_active_ezshare_ssid():

    devices = nmcli.device.wifi()
    for device in devices:
        if "ez Share" in device.ssid:
            logging.info(f"'{device.ssid}' is online!")
            return device.ssid


def connect_to_ezshare_ssid(ssid):
    try:
        logging.info(f"Going to connect to '{ssid}'")
        nmcli.device.wifi_connect(ssid=ssid, password=_PASSWORD)
        logging.info(f"Connected to '{ssid}'")
    except Exception as e:
        logging.error(f"Error connecting to '{ssid}': {e}")
        raise e


def get_list_of_filenames_on_card():
    domain = "http://ezshare.card/"
    url = domain + "dir?dir=A:"

    list_of_filenames = []

        
    try:
        list_of_filenames = get_list_of_filenames_on_card_dir("A:")
    except Exception as e:
        logging.error(f"Error parsing list of files from camera: {e}")
        raise e

    logging.info(f"Retrieved a list of {len(list_of_filenames)} files that are on the card")
    return list_of_filenames

def get_list_of_filenames_on_card_dir(dir):
    domain = "http://ezshare.card/dir?dir="
    url = domain + dir

    list_of_filenames = []

    try:
        logging.debug(f"Loading '{url}'")
        with requests.get(url) as req:
            html = req.content
    except Exception as e:
        logging.error(f"Error downloading list of files from camera: {e}")
        raise e
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # parse image files
        for a_tag in soup.select('a'):
            if a_tag.text == " ." or a_tag.text == " .." or a_tag.text == " .Trashes" or a_tag.text == " .Spotlight-V100" or a_tag.text == " .fseventsd":
                logging.debug(f"Skipping dir: {a_tag}")
                continue

            href = a_tag.attrs['href']
            # import pdb; pdb.set_trace()
            if href.find("dir") >= 0:
                logging.debug(f"Found dir: {href}")
                new_dir = href[href.find("=")+1:]
                dir_list = get_list_of_filenames_on_card_dir(new_dir)
                newlist = list_of_filenames + dir_list
                list_of_filenames = newlist
            if href.find("download") >= 0:
                filename = a_tag.text[1:]
                directory = dir[5:]
                logging.debug(f"File on card: {filename[1:]}")
                list_of_filenames.append((directory, filename))
    except Exception as e:
        logging.error(f"Error parsing list of files from camera: {e}")
        raise e

    logging.info(f"Retrieved a list of {len(list_of_filenames)} files that are on the card")
    return list_of_filenames



def download(directory, filename):
    logging.info(f"Going to download dir:{directory} file: {filename}")
    domain = "http://ezshare.card/download?file="
    if directory != "":
        url = domain + directory + "%5C" + filename
    else:
        url = domain + filename

    try:
        # download to {_TEMP}
        directory_local = directory.replace("%5C", "/")
        os.makedirs(f"{_DESTINATION}/{directory_local}", exist_ok=True)
        filepath = f"{_DESTINATION}/{directory_local}/{filename}"

        logging.info(f"Going to download {url}")
        sleep = 1
        for attempt in range(10):
            try:
                logging.info(f"Downloading {url}")
                with requests.get(url, allow_redirects=True, timeout=10.0) as req:
                    blob = req.content
                open(filepath, 'wb').write(blob)
            except Exception as e:
                time.sleep(sleep)  # pause hoping things will normalize
                logging.warning(f"Sleeping {sleep} seconds because of error trying to download {url} ({e}).")
                sleep *= 2
            else:
                logging.info(f"Downloaded '{filepath}'")
                break  # no error caught
        else:
            logging.critical(f"Retried 10 times downloading {url}")
        return True
    except Exception as e:
        logging.error(f"Error downloading '{filename}': {e}")
        logging.error(traceback.format_exc())
        return False

def connect_to_home_network(name):
    try:
        nmcli.connection.up(name)
        logging.info(f"Reconnected to home network '{name}'")
    except Exception as e:
        logging.error(f"Error reconnecting to home network '{name}': {e}")
        # don't propagate, this function is in other exception handlers
        # and that seems to cause problems

if __name__ == "__main__":
    # main()
    main_nowifi()
