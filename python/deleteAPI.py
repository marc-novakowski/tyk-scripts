#!/usr/bin/python3

import json
import os
import getopt
import sys
sys.path.append(f'{os.environ.get("HOME")}/code/tyk-scripts/module')
import tyk

scriptName = os.path.basename(__file__)

def printhelp():
    print(f'{scriptName} --dashboard <dashboard URL> --cred <Dashboard API credentials> --apiid <apiid>')
    print("    Will delete the API with apiid from the dashboard")
    sys.exit(1)

dshb = ""
auth = ""
apiid = ""
verbose = 0

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["help", "dashboard=", "cred=", "apiid=", "verbose"])
except getopt.GetoptError:
    printhelp()

for opt, arg in opts:
    if opt == '--help':
        printhelp()
    elif opt == '--dashboard':
        dshb = arg.strip().strip('/')
    elif opt == '--cred':
        auth = arg
    elif opt == '--apiid':
        apiid = arg
    elif opt == '--verbose':
        verbose = 1

if not (dshb and auth and apiid):
    printhelp()

dashboard = tyk.dashboard(dshb, auth)

resp = dashboard.deleteAPI(apiid)
print(json.dumps(resp.json()))
if resp.status_code != 200:
    sys.exit(1)
