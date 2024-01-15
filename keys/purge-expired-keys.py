#!/usr/bin/python3

# This is a script to help with tidying up unwanted Tyk API keys directly from Redis.
# It does not use tyk APIs at all.
# It supports both delete or list mode. Use the --list option to explore what keys exist and what ones should
# be deleted before replacing --list with --delete to purge the unwanted keys.

# For caution the orgid of the keys to be considered must be given even when there is only one org id in redis.

# Keys have an expiry timestamp in epoch seconds. Keys which expired before the timestamp given in --epoch will
# be considered for listing or deletion.

# The selected keys can be further narrowed down using the --policy and --api options. Either or both can be given.
# Only apikeys which match the given --policy and/or --api options will be included but only at most one of each can be given.

# USE THIS OPTION WITH CAUTION: '--epoch 0'
# Keys with an expiry of 0 are set to never expire. They are dealt with as a special case and only considered
# when '--epoch 0' is given.
# Using the --api and --policy options will allow the non-expiring keys for a particular API or policy to be removed
# when they are combined with '--epoch 0'

# USE THIS OPTION WITH CAUTION: --include-jwt-sessions
# --include-jwt-sessions means that keys created as JWT session objects will be considered for deletion.
# Deleting these will allow them to be recreated when a JWT with the corresponding sub is presented 
# as an auth token to the gateway. This is almost certainly not what you want.
# For example: 
#    JWT auth is setup with a policy that defaults to a 1 hour key life.
#    A JWT is presented with a particular subject and the corresponding key is created.
#    That key expires after an hour and access is denied when the JWT is presented
#    This script is used to remove that expired key
#    The JWT is presented again and the corresponding key is created allowing access for another hour
#    So removing the key has restored access via the JWT rather than blocking it

# The script is not redis cluster aware. It must be pointed at a master redis replica (if replication is active)
# If redis is sharded the script must be used on each master in turn

# Be aware that the database may change between --list and --delete in a live environment

## THIS SCRIPT IS UNSUPPORTED AT ANY LEVEL
## THIS SCRIPT IS UNSUPPORTED AT ANY LEVEL
## THIS SCRIPT IS UNSUPPORTED AT ANY LEVEL

import redis
import json
import sys
import getopt
import datetime
import os
import threading
import logging

listKeys = 0
deleteKeys = 0
dumpJSON = False
includeJWTsessions = 0

maxAge = -1
host = ""
port = ""
delpol = None
delapi = None
orgid = None
redisPassword = None

# Use logger instead of print so output from threads does not get interleaved
logging.basicConfig(format='%(message)s', level=logging.INFO, stream=sys.stdout)

scriptName = os.path.basename(__file__)

def printhelp():
    print(f'{scriptName} [--delete|--list] --host <hostname> --port <portnum> --password <redisPassword> --epoch <epoch> --orgid <orgid> --api <APIID> --policy <POLICYID> --include-jwt-sessions --dump')
    sys.exit(2)

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["help", "delete", "list", "dump", "epoch=", "host=", "port=", "password=", "api=", "policy=", "orgid=", "include-jwt-sessions"])
except getopt.GetoptError:
    printhelp()

for opt, arg in opts:
    if opt == '--delete':
        deleteKeys = 1
    elif opt == '--list':
        listKeys = 1
    elif opt == '--dump':
        dumpJSON = True
    elif opt == '--epoch':
        maxAge = int(arg)
    elif opt == '--host':
        host = arg
    elif opt == '--port':
        port = arg
    elif opt == '--api':
        delapi = arg
    elif opt == '--policy':
        delpol = arg
    elif opt == '--orgid':
        orgid = arg
    elif opt == '--password':
        redisPassword = arg
    elif opt == '--include-jwt-sessions':
        includeJWTsessions = 1

if deleteKeys and listKeys:
    print('Cannot both list and delete keys. Choose one')
    printhelp()

if not (deleteKeys or listKeys):
    print('Must specify delete or list')
    printhelp()

if dumpJSON and not listKeys:
    print('Can only dump apikey JSON when --list is used')
    printhelp()

if maxAge < 0:
    print('Must specify epoch second cutoff for keys to be deleted. Use 0 to target just non-expiring keys which are otherwise ignored')
    printhelp()

if not host:
    host="127.0.0.1"

if not port:
    port="6379"

if not orgid:
    print('Must specify an orgid')
    printhelp()

def shoulddel(apikey, apiid, polid, orgid):
    if orgid != apikey['org_id']:
        # logging.info(f"Orgid mismatch: {orgid!r} != {apikey['org_id']!r}")
        return False
    if apiid is not None:
        if apiid not in apikey['access_rights']:
            # logging.info(f"apiid mismatch: {apiid!r} not in {apikey['access_rights']!r}")
            return False
    if polid is not None:
        if apikey['apply_policies'] is not None:
            if polid not in apikey['apply_policies']:
                # logging.info(f"polid mismatch: {polid} not in {apikey['apply_policies']!r}")
                return False
        else:
            # polid is defined but the apikey has no policy. No match
            return False
    #if apikey['meta_data']['TykJWTSessionID'] is not None and not includeJWTsessions:
    if 'TykJWTSessionID' in apikey['meta_data'] and not includeJWTsessions:
        # This key is a JWT session for a particular sub. Deleting it will mean it just gets recreated on the next call
        return False
    return True

logging.info(f"Attempting to connect to redis on {host}:{port}")
r = redis.StrictRedis(host=host, port=port, db=0, password=redisPassword)
info = r.info()
logging.info(f"Keys: {info['db0']['keys']}")

rep = info('Replication')
if 'role' in rep:
    role=rep['role']
    if role == 'slave':
        logging.info(f"[FATAL]Node is a replica, must connect to a master node {rep['master_host']}:{rep['master_port']}")
        sys.exit(2)

maxDateTime = datetime.datetime.fromtimestamp( maxAge )
logging.info(f"Searching for keys that expired before {maxAge}, ({maxDateTime})")

def execute_pipeline(get_pipeline, del_pipeline, keys_to_get):
    deletedKeys = 0
    pipeline_size = 0
    values = get_pipeline.execute()
    for i in range(0, len(keys_to_get)):
        apikey = json.loads(values[i])
        key = keys_to_get[i]
        keyString = key.decode('utf-8')
        expires = int(apikey["expires"])
        if maxAge > 0:
            # ignore the ones with 'expires' less than or equal to 0, they are the non-expiring api keys
            if expires <= 0:
                # skip because this is a non-expiring key
                continue
            elif expires <= maxAge:
                if shoulddel(apikey, delapi, delpol, orgid):
                    if listKeys:
                        deletedKeys += 1
                        expiresDateTime = datetime.datetime.fromtimestamp( expires )
                        logging.info(f"{keyString} expires {expires} ({expiresDateTime}) <= {maxAge} ({maxDateTime}) {apikey["alias"]}")
                        if dumpJSON:
                            logging.info(json.dumps(apikey, indent=4, sort_keys=True))
                    else:
                        expiresDateTime = datetime.datetime.fromtimestamp( expires )
                        logging.info(f"Deleting: {keyString} expires {expires} ({expiresDateTime}) <= {maxAge} ({maxDateTime}) {apikey["alias"]}")
                        del_pipeline.delete(key)
                        deletedKeys += 1
                        pipeline_size += 1
        else:
            # list or delete all the non-expiring keys (maxAge == 0 and expires <= 0)
            if expires <= 0:
                if shoulddel(apikey, delapi, delpol, orgid):
                    if listKeys:
                        deletedKeys += 1
                        logging.info(keyString, expires, '<=', maxAge)
                        if dumpJSON:
                            logging.info(json.dumps(apikey, indent=4, sort_keys=True))
                    else:
                        logging.info('Deleting: ', keyString, expires, '<=', maxAge)
                        r.delete(key)
                        deletedKeys += 1
    if pipeline_size > 0:
        del_pipeline.execute()
    return deletedKeys


def iterate_keys(stop_event, prefix):

    total = 0
    deletedKeys = 0

    get_pipeline = r.pipeline(transaction=False)
    del_pipeline = r.pipeline(transaction=False)
    keys_to_get = []

    for key in r.scan_iter(match="apikey-"+prefix+"*", count=5000):
        # Check for stop event to exit the thread
        if stop_event.is_set():
            logging.info(f"Exiting thread {prefix} after processing {total} keys")
            del_pipeline.execute()
            return

        total += 1
        get_pipeline.get(key)
        keys_to_get.append(key)
        if len(keys_to_get) < 100:
            continue
        deletedKeys = deletedKeys + execute_pipeline(get_pipeline, del_pipeline, keys_to_get)
        keys_to_get = []
    deletedKeys = deletedKeys + execute_pipeline(get_pipeline, del_pipeline, keys_to_get)

    logging.info(f"{total} total keys")
    if listKeys:
        logging.info(f"{deletedKeys} keys listed")
    else:
        logging.info(f"{deletedKeys} keys deleted")

kill_event = threading.Event()
threads = []

for i in range(0, 16):
    prefix = hex(i)[2:]
    x = threading.Thread(target=iterate_keys, args=(kill_event, prefix))
    threads.append(x)

for t in threads:
    t.start()

try:
    for t in threads:
        t.join()
    logging.info("All threads finished")
except:
    logging.info('User exit requested')
    kill_event.set()
    for t in threads:
        t.join()
