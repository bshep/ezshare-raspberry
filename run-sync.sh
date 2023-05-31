#!/bin/bash

/home/pi/ezshare-raspberry/ezshare.py -m once && rsync -zaP /home/pi/sdcard-sync/ /mnt/cpap
