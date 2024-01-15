#!/usr/bin/python3

# Gather stats on how much time is left for API keys to expire in redis

import redis
import json
import sys
import getopt
import datetime
import os
import time


listedKeys = 0
host = ""
port = ""
delpol = None
delapi = None
redisPassword = None

scriptName = os.path.basename(__file__)

def printhelp():
    print(f'{scriptName} --host <hostname> --port <portnum> --password <redisPassword> --api <APIID> --policy <POLICYID>')
    sys.exit(2)

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["help", "host=", "port=", "password=", "api=", "policy="])
except getopt.GetoptError:
    printhelp()

for opt, arg in opts:
    if opt == '--epoch':
        maxAge = int(arg)
    elif opt == '--host':
        host = arg
    elif opt == '--port':
        port = arg
    elif opt == '--api':
        delapi = arg
    elif opt == '--policy':
        delpol = arg
    elif opt == '--password':
        redisPassword = arg

if not host:
    host="127.0.0.1"

if not port:
    port="6379"


print(f"Attempting to connect to redis on {host}:{port}")
r = redis.StrictRedis(host=host, port=port, db=0, password=redisPassword)
info = r.info()
print(f"Keys: {info['db0']['keys']}")

rep = r.info('Replication')
if 'role' in rep:
    role=rep['role']
    if role == 'slave':
        print(f"[FATAL]Node is a replica, must connect to a master node {rep['master_host']}:{rep['master_port']}")
        sys.exit(2)

maxDateTime = datetime.datetime.fromtimestamp( maxAge )

total = 0
for key in r.scan_iter(match="apikey-*", count=5000):
    total += 1
    # For larger data sets, only sample 1% of the keys
    if (total % 100) != 0:
        continue
    if (total % 1000) == 0:
        print(f'Processed {total} keys, percentage {total/info["db0"]["keys"]:.2%}')
    keyString = key.decode('utf-8')
    apikey = json.loads(r.get(key))
    expires = int(apikey["expires"])

    # TODO: only supports policy match now, could also match on API key if needed
    if apikey['apply_policies'] is not None:
        if delpol in apikey['apply_policies']:
            secondsUntilExpire = expires - time.time()
            print(f"{keyString},{secondsUntilExpire}")
            listedKeys += 1

print(total, " total keys")
print(listedKeys, 'keys surveyed')
