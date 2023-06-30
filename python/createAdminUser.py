#!/usr/bin/python3

###############################################################
# Reference for calling the dashboard.createAdminUser
# arguments are dashboard, dashboard API key, admin secret, orgid, username, user password
###############################################################

import json
import requests
import os
import getopt
import sys
import time
sys.path.append(f'{os.path.abspath(os.path.dirname(__file__))}/module')
import tyk

# Suppress the warnings from urllib3 when using a self signed certs
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

scriptName = os.path.basename(__file__)

def printhelp():
    print(f'{scriptName} --dashboard <dashboard URL> --adminsecret <Dashboard Admin Secret> --useremail <user email> --userpass <user password>')
    print("    Create an admin user in all orgs in the dashboard instance")
    sys.exit(1)

dshb = ""
auth = ""
useremail = ""
userpass = ""
verbose = 0
adminsecret = ""

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["help", "dashboard=", "adminsecret=", "useremail=", "userpass=", "number=", "verbose"])
except getopt.GetoptError as opterr:
    print(f'Error in option: {opterr}')
    printhelp()

for opt, arg in opts:
    if opt == '--help':
        printhelp()
    elif opt == '--dashboard':
        dshb = arg.strip().strip('/')
    elif opt == '--adminsecret':
        adminsecret = arg
    elif opt == '--useremail':
        useremail = arg
    elif opt == '--userpass':
        userpass = arg
    elif opt == '--verbose':
        verbose = 1

if not (dshb and useremail and userpass and adminsecret):
    printhelp()

dashboard = tyk.dashboard(dshb, "", adminsecret)

organisations = dashboard.getOrganisations().json()
for org in organisations["organisations"]:
    resp = dashboard.createAdminUser(useremail, userpass, org["id"])
    print(resp.json())
