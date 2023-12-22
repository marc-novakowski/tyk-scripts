# A module to speed up writing scripts to do stuff with the tyk dashboard
# This is not supported by anyone at any level but is just my efforts to make my life easier
# USE AT YOUR OWN RISK

import json
import requests
import time
import uuid

# Suppress the warnings from urllib3 when using a self signed certs
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

###################### BASE CLASS ######################
# mostly for functions to print stuff out
class tyk:
    def printUserSummaryHeader(self):
        print('# ID,IsActive,org_id,first_name,last_name,email,IsAdmin,accessKey')

    def printUserSummary(self, user):
        if not "IsAdmin" in user["user_permissions"]:
            user["user_permissions"]["IsAdmin"] = "notAdmin"
        print(f'{user["id"]},{user["active"]},{user["org_id"]},{user["first_name"]},{user["last_name"]},{user["email_address"]},{user["user_permissions"]["IsAdmin"]},{user["access_key"]}')

    def printKeySummaryHeader(self):
        print('# Key; alias; policyID(s); API(s)')

    def printKeySummary(self,key):
        if "key_id" in key:
            print(f'{key["key_id"]};{key["data"]["alias"]}',end='')
        else:
            print(f'{key["key_hash"]};{key["data"]["alias"]}',end='')
        firstPolicy=True
        if "apply_policies" in key["data"] and key["data"]["apply_policies"] is not None:
            for policy in key["data"]["apply_policies"]:
                if firstPolicy:
                    print(f';{policy}',end='')
                    firstPolicy=False
                else:
                    print(f',{policy}',end='')
        else:
            print(';',end='')
        if "access_rights" in key["data"] and key["data"]["access_rights"] is not None:
            firstAPI=True
            for api in key["data"]["access_rights"]:
                if firstAPI:
                    print(f';{api}',end='')
                    firstAPI=False
                else:
                    print(f',{api}',end='')
        else:
            print(';',end='')
        print('')

    def printPolicySummaryHeader(self):
        print('# Name; policyID; API, API, ...')

    def printPolicySummary(self,policy):
        if policy["id"] == "":
            policy["id"] = policy["_id"]
        print(f'{policy["name"]};{policy["id"]}',end='')
        if "access_rights" in policy and policy["access_rights"] is not None:
            firstAPI=True
            for api in policy["access_rights"]:
                if firstAPI:
                    print(f';{api}',end='')
                    firstAPI=False
                else:
                    print(f',{api}',end='')
            print('')
        else:
            print(',')

###################### DASHBOARD CLASS ######################
class dashboard(tyk):
    def __init__(self, URL, authKey, adminSecret = 'N/A' , description = 'N/A'):
        self.URL = URL.strip('/')       # The dashboard URL
        self.authKey = authKey          # User key to authenticate API calls
        self.description = description  # description of this dashboard
        self.adminSecret = adminSecret  # The admin secret for the admin API (admin_secret in tyk_analytics.conf, AdminSecret in tyk.conf)

    def __str__(self):
        return f'Dashboard URL: {self.URL}, Auth token: {self.authkey}, Admin Secret: {self.adminSecret}, Description: {self.description}'

    def __repr__(self):
        return f'tyk.dashboard("{self.URL}", "{self.authkey}", "{self.adminSecret}", "{self.description}")'

    def url(self):
        return self.URL

    def authkey(self):
        return self.authkey

    def setAuthkey(self, authkey):
        self.authkey = authkey
        return self.authkey

    def description(self):
        return self.description

    def adminSecret(self):
        return self.adminSecret

    def setAdminSecret(self, adminSecret):
        self.adminSecret = adminSecret
        return adminSecret


    # Dashboard API functions

    # Dashboard getAPI
    def getAPI(self, APIid):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/apis/{APIid}', headers=headers, verify=False)

    # Dashboard getAPIs
    def getAPIs(self):
        headers = {'Authorization' : self.authKey}
        response = requests.get(f'{self.URL}/api/apis/?p=-1', headers=headers, verify=False)
        body_json = response.json()
        if response.status_code == 200:
            # pull the APIs out of the 'apis' array so that the format is the same as it is from the gateway
            # also extract the API defintions out of 'api_definition' and add it to the array
            apis = []
            for api in body_json['apis']:
                apis.append(api['api_definition'])
            response._content = json.dumps(apis).encode()
        return response

    # Dashboard standardise the API JSON format
    def standardiseAPI(self, APIdefinition):
        # the dashboard needs to have a key called 'api_definition' with the api_definition in it
        # but sometimes the json is just the API definition. So test for that and set it right
        if not 'api_definition' in APIdefinition:
            APIDict = dict()
            APIDict['api_definition'] = APIdefinition
            APIdefinition = APIDict
        return APIdefinition

    # Dashboard __createAPI
    def __createAPI(self, APIdefinition):
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/api/apis', data=APIdefinition, headers=headers, verify=False)

    # Dashboard createAPI
    def createAPI(self, APIdefinition):
        APIdefinition = self.standardiseAPI(APIdefinition)
        if isinstance(APIdefinition, dict):
            APIdefinition = json.dumps(APIdefinition)
        return self.__createAPI(APIdefinition)

    # Dashboard createAPIs
    def createAPIs(self, APIdefinition, numberToCreate):
        APIdefinition = self.standardiseAPI(APIdefinition)
        # create a dictionary of all API names
        apis = self.getAPIs().json()
        APIName = APIdefinition['api_definition']['name']
        allnames = dict()
        for api in apis:
            allnames[api['name']] = 1
        i = 1
        numberCreated = 0
        while numberCreated < numberToCreate:
            # work out the next free name (format is name-i)
            while APIName+str(i) in allnames:
                i += 1
            newname=APIName+str(i)
            allnames[newname] = 1
            APIdefinition['api_definition']['name'] = newname
            APIdefinition['api_definition']['slug'] = newname
            APIdefinition['api_definition']['proxy']['listen_path'] = '/'+newname+'/'
            print(f'Adding API {APIdefinition["api_definition"]["name"]}, {APIdefinition["api_definition"]["proxy"]["listen_path"]}')
            response = self.__createAPI(json.dumps(APIdefinition))
            print(response.json())
            # if a call fails, stop and return the number of successes
            if response.status_code != 200:
                break
            numberCreated += 1
        return numberCreated

    # Dashboard updateAPI
    def updateAPI(self, APIdefinition, APIid):
        if isinstance(APIdefinition, dict):
            APIdefinition = json.dumps(APIdefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.put(f'{self.URL}/api/apis/{APIid}', data=APIdefinition, headers=headers, verify=False)

    # Dashboard deleteAPI
    def deleteAPI(self, APIid):
        headers = {'Authorization' : self.authKey}
        return requests.delete(f'{self.URL}/api/apis/{APIid}', headers=headers, verify=False)

    # Dashboard deleteAllAPIs
    def deleteAllAPIs(self):
        allDeleted = True
        apis = self.getAPIs().json()
        for api in apis:
            print(f'Deleting API: {api["name"]}: {api["api_id"]}')
            response = self.deleteAPI(api['api_id'])
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted


    # Dashboard Policy functions
    # Dashboard getPolicy
    def getPolicy(self, policyID):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/portal/policies/{policyID}', headers=headers, verify=False)

    # Dashboard getPolicies
    def getPolicies(self):
        headers = {'Authorization' : self.authKey}
        response = requests.get(f'{self.URL}/api/portal/policies/?p=-1', headers=headers, verify=False)
        if response.status_code == 200:
            body_json = response.json()
            # rename 'Data' to 'polcies' to be consistent with apis, users and keys.
            body_json['policies'] = body_json['Data']
            del body_json['Data']
            response._content = json.dumps(body_json).encode()
        return response

    # Dashboard createPolicy
    def createPolicy(self, policyDefinition):
        if isinstance(policyDefinition, dict):
            policyDefinition = json.dumps(policyDefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/api/portal/policies', data=policyDefinition, headers=headers, verify=False)

    # Dashboard createPolicies
    def createPolicies(self, policyDefinition, APIid, numberToCreate):
        policies = self.getPolicies().json()
        # create a dictionary of all policy names
        PolicyName = policyDefinition['name']
        allnames = dict()
        for policy in policies:
            allnames[policy['name']] = 1
        i = 1
        numberCreated = 0
        while numberCreated < numberToCreate:
            # work out the next free name (format is name-i)
            while PolicyName+str(i) in allnames:
                i += 1
            newname=PolicyName+str(i)
            allnames[newname] = 1
            policyDefinition['name']=PolicyName+str(i)
            policyDefinition['access_rights_array'] = json.loads('[{ "api_id": "' + APIid + '", "versions": [ "Default" ], "allowed_urls": [], "restricted_types": [], "limit": null, "allowance_scope": "" }]')
            print(f'Creating policy: {policyDefinition["name"]}')
            response = self.createPolicy(json.dumps(policyDefinition))
            print(response.json())
            # if a call fails, stop and return the number of successes
            if response.status_code != 200:
                break
            numberCreated += 1
        return numberCreated

    # Dashboard updatePolicy
    def updatePolicy(self, policyDefinition, policyID):
        if isinstance(policyDefinition, dict):
            policyDefinition = json.dumps(policyDefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.put(f'{self.URL}/api/portal/policies/{policyID}', data=policyDefinition, headers=headers, verify=False)

    # Dashboard deletePolicy
    def deletePolicy(self, policyID):
        headers = {'Authorization' : self.authKey}
        return requests.delete(f'{self.URL}/api/portal/policies/{policyID}', headers=headers, verify=False)

    # Dashboard deleteAllPolicies
    def deleteAllPolicies(self):
        allDeleted = True
        policies = self.getPolicies().json()
        for policy in policies['policies']:
            print(f'Deleting policy: {policy["_id"]}')
            response = self.deletePolicy(policy['_id'])
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted


    # Dashboard Key functions

    # Two options for getting all the keys
    # /api/apis/keys/?p=-1 which just lists the key IDs
    # /api/keys/detailed/?p=-1 which dump the details of all the keys

    # Dashboard getKeys
    def getKeys(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/apis/-/keys?p=-1', headers=headers, verify=False)

    # Dashboard getKeysDetailed
    def getKeysDetailed(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/keys/detailed/?p=-1', headers=headers, verify=False)

    # Dashboard getKey
    def getKey(self, keyID):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/apis/-/keys/{keyID}', headers=headers, verify=False)

    # Dashboard createKey
    def createKey(self, keyDefinition):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/api/keys', data=keyDefinition, headers=headers, verify=False)

    # Dashboard createCustomKey
    def createCustomKey(self, keyDefinition, keyID):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/api/keys/{keyID}', data=keyDefinition, headers=headers, verify=False)

    # Dashboard updateKey
    def updateKey(self, keyDefinition, keyID):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.put(f'{self.URL}/api/keys/{keyID}', data=keyDefinition, headers=headers, verify=False)

    # Dashboard deleteKey
    def deleteKey(self, keyID):
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        # not sure where ?auto_guess=true comes from but it works when keys are encrypted
        return requests.delete(f'{self.URL}/api/keys/{keyID}/?auto_guess=true', headers=headers, verify=False)

    # Dashboard deleteAllKeys
    def deleteAllKeys(self):
        allDeleted = True
        keys = self.getKeys().json()
        for key in keys['data']['keys']:
            keyID = key['key_id']
            print(f'Deleting key: {keyID}')
            response = self.deleteKey(keyID)
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted

    # Dashboard keyExists
    def keyExists(self, keyID):
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        resp = requests.get(f'{self.URL}/api/apis/-/keys/{keyID}', headers=headers, verify=False)
        return resp.status_code == 200


    # Dashboard Portal Catalogue functions

    # Dashboard getCatalogue
    def getCatalogue(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/portal/catalogue', headers=headers, verify=False)

    # Dashboard updateCatalogue
    def updateCatalogue(self, catalogue):
        if isinstance(catalogue, dict):
            catalogue = json.dumps(catalogue)
        headers = {'Authorization' : self.authKey}
        return requests.put(f'{self.URL}/api/portal/catalogue', data=catalogue, headers=headers, verify=False)


    # Dashboard Organisation functions

    # Dashboard getOrganisations
    def getOrganisations(self):
        headers = {'admin-auth': self.adminSecret}
        headers['Content-Type'] = 'application/json'
        return requests.get(f'{self.URL}/admin/organisations?p=-1', headers=headers, verify=False)

    # Dashboard getOrganisation
    def getOrganisation(self, orgID):
        headers = {'admin-auth': self.adminSecret}
        headers['Content-Type'] = 'application/json'
        return requests.get(f'{self.URL}/admin/organisations/{orgID}', headers=headers, verify=False)

    # Dashboard createOrganisation
    def createOrganisation(self, orgDefinition):
        if isinstance(orgDefinition, dict):
            orgDefinition = json.dumps(orgDefinition)
        headers = {'admin-auth': self.adminSecret}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/admin/organisations', data=orgDefinition, headers=headers, verify=False)

    # Dashboard createOrganisations
    def createOrganisations(self, orgDefinition, numberToCreate):
        orgs = self.getOrganisations().json()
        # create a dictionary of all policy names
        orgSlug = orgDefinition['owner_slug']
        orgOwner = orgDefinition['owner_name']
        allSlugs = dict()
        for org in orgs['organisations']:
            allSlugs[org['owner_slug']] = 1
        i = 1
        numberCreated = 0
        while numberCreated < numberToCreate:
            # work out the next free name (format is name-i)
            while orgSlug+str(i) in allSlugs:
                i += 1
            newSlug=orgSlug+str(i)
            allSlugs[newSlug] = 1
            orgDefinition['owner_name']=orgOwner+str(i)
            orgDefinition['owner_slug']=orgSlug+str(i)
            print(f'Creating Organisation: {orgDefinition["owner_slug"]}')
            response = self.createOrganisation(json.dumps(orgDefinition))
            print(response.json())
            # if a call fails, stop and return the number of successes
            if response.status_code != 200:
                break
            numberCreated += 1
        return numberCreated

    # Dashboard deleteOrganisation
    def getOrganisation(self, orgID):
        headers = {'admin-auth': self.adminSecret}
        headers['Content-Type'] = 'application/json'
        return requests.delete(f'{self.URL}/admin/organisations/{orgID}', headers=headers, verify=False)


    # Dashboard User functions

    # Dashboard createAdminUser
    def createAdminUser(self, userEmail, userPass, orgID):
        headers = {'admin-auth': self.adminSecret}
        headers['Content-Type'] = 'application/json'
        userDefinition = {
                'first_name': 'Tyk',
                'last_name': 'Admin',
                'email_address': userEmail,
                'password': userPass,
                'active': True,
                'org_id': orgID,
                'user_permissions': { 'ResetPassword' : 'admin', 'IsAdmin': 'admin' }}
        createResp = requests.post(f'{self.URL}/admin/users', data=json.dumps(userDefinition), headers=headers, verify=False)
        if createResp.status_code != 200:
            return createResp
        # need to set the user password immediately
        userdata = createResp.json()
        headers = {'Authorization' : userdata['Meta']['access_key']}
        headers['Content-Type'] = 'application/json'
        resetResp = requests.post(f'{self.URL}/api/users/{userdata["Meta"]["id"]}/actions/reset', data='{"new_password":"'+userPass+'"}', headers=headers, verify=False)
        return createResp

    # Dashboard getUsers
    def getUsers(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/users?p=-1', headers=headers, verify=False)

    # Dashboard getUser
    def getUser(self, userid):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/users/{userid}', headers=headers, verify=False)

    # Dashboard deleteUser
    def deleteUser(self, userid):
        headers = {'Authorization' : self.authKey}
        return requests.delete(f'{self.URL}/api/users/{userid}/actions/key/reset', headers=headers, verify=False)

    # Dashboard resetAdminKey
    def resetAdminKey(self, userid):
        headers = {'Authorization' : self.authKey}
        return requests.put(f'{self.URL}/api/users/{userid}/actions/key/reset', headers=headers, verify=False)

    # Dashboard resetUserPassword
    def resetUserPassword(self, userid, userPass):
        headers = {'Authorization' : self.authKey}
        return requests.post(f'{self.URL}/api/users/{userid}/actions/reset', data='{"new_password":"'+userPass+'"}', headers=headers, verify=False)


    # Dashboard Licence functions

    # Dashboard setLicence
    def setLicence(self, licence):
        headers = {'Content-Type' : 'application/x-www-form-urlencoded'}
        return requests.post(f'{self.URL}/license', data=f'license={licence}', headers=headers, verify=False)


    # Dashboard Bootstrap functions

    # Dashboard bootstrap. Takes an admin email, admin password, a dashboard licence and an optional portal cname.
    def bootstrap(self, userEmail, userPass, licence, cname = "portal.cname.com"):
        # set the licence
        response = self.setLicence(licence)
        if response.status_code != 200:
            print("[FATAL]licence cannot be set")
            return response
        # create the org
        orgDef = { "owner_name": userEmail, "owner_slug": "slug", "cname_enabled": True, "cname": cname}
        response = self.createOrganisation(orgDef)
        if response.status_code != 200:
            print("[FATAL]Failed to create organisation")
            return response
        orgID = response.json()["Meta"]
        response = self.createAdminUser(userEmail, userPass, orgID)
        return response



    # Dashboard Analytics functions

    # Dashboard getAPIUsage
    def getAPIUsage(self, startday = time.strftime('%d'), startmonth = time.strftime('%m'), startyear = time.strftime('%Y'), endday = time.strftime('%d'), endmonth = time.strftime('%m'), endyear = time.strftime('%Y')):
        # Get the usage of all APIs for a period (defaults to today)
        if isinstance(startday, int):
            startday = str(startday)
        if isinstance(startmonth, int):
            startmonth = str(startmonth)
        if isinstance(startyear, int):
            startyear = str(startyear)
        if isinstance(endday, int):
            endday = str(endday)
        if isinstance(endmonth, int):
            endmonth = str(endmonth)
        if isinstance(endyear, int):
            endmonth = str(endyear)
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/usage/apis/{startday}/{startmonth}/{startyear}/{endday}/{endmonth}/{endyear}?by=Hits&sort=1&p=-1', headers=headers, verify=False)

    # Dashboard Certificate functions

    # Dashboard getCerts
    def getCerts(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/certs?p=-1', headers=headers, verify=False)

    # Dashboard getCert
    def getCert(self, certid):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/certs/{certid}', headers=headers, verify=False)

    # Dashboard getCertsDetails
    def getCertsDetails(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/certs?p=-1&mode=detailed', headers=headers, verify=False)

    # Dashboard createCert
    def createCert(self, certFile):
        headers = {'Authorization' : self.authKey}
        files={'data': open(certFile,'r')}
        return requests.post(f'{self.URL}/api/certs', files=files, headers=headers, verify=False)

    # Dashboard deleteCert
    def deleteCert(self, certid):
        headers = {'Authorization' : self.authKey}
        return requests.delete(f'{self.URL}/api/certs/{certid}', headers=headers, verify=False)

    # Dashboard deleteAllCerts
    def deleteAllCerts(self):
        allDeleted = True
        certs = self.getCerts().json()
        print(certs)
        for certid in certs['certs']:
            print(f'Deleting certificate: {certid}')
            response = self.deleteCert(certid)
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted

    # Dashboard System functions

    # Dashboard getNodes
    def getNodes(self):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/system/nodes?p=-1', headers=headers, verify=False)

    # Dashboard getSystemStats
    def getSystemStats(self, ):
        headers = {'Authorization' : self.authKey}
        return requests.get(f'{self.URL}/api/system/stats', headers=headers, verify=False)

    # Dashboard getSystemStauts
    def getSystemStatus(self):
        return requests.get(f'{self.URL}/hello/', verify=False)

    # Dashboard is up
    def isUp(self):
        try:
            response = self.getSystemStatus()
            return response.status_code == 200
        except:
            return False

    # Dashboard wait to be up
    def waitUp(self, timeout = 0):
        count = 0
        if timeout > 0:
            while (not self.isUp() and count < timeout):
                time.sleep(1)
                count += 1
        else:
            while not self.isUp():
                time.sleep(1)
        return self.isUp()



###################### GATEWAY CLASS ######################
class gateway(tyk):
    def __init__(self, URL, authKey, description = 'N/A'):
        self.URL = URL.strip('/')       # The gateway URL
        self.authKey = authKey          # User key to authenticate API calls ('Secret' from tyk.conf)
        self.description = description  # description of this gateway

    def __str__(self):
        return f'Gateway URL: {self.URL}, Auth token: {self.authkey}, Description: {self.description}'

    def __repr__(self):
        return f'tyk.gateway("{self.URL}", "{self.authkey}", "{self.description}")'

    def url(self):
        return self.URL

    def authkey(self):
        return self.authkey

    def setAuthkey(self, authkey):
        self.authkey = authkey
        return self.authkey

    def description(self):
        return self.description

    # Gateway API functions

    # Gateway reloadGroup
    def reloadGroup(self):
        headers = {'x-tyk-authorization' : self.authKey}
        response = requests.get(f'{self.URL}/tyk/reload/group', headers=headers, verify=False)
        if response.status_code != 200:
            print(f'[WARN]The group hot reload failed with code {response.status_code}: {response.json()}')
        return response

    # Gateway getAPI
    def getAPI(self, APIid):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/apis/{APIid}', headers=headers, verify=False)

    # Gateway getAPIs
    def getAPIs(self):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/apis', headers=headers, verify=False)

    # Gateway standardise the API JSON format and always return a dict
    def standardiseAPI(self, APIdefinition):
        # the gateway must not have a key called 'api_definition' with the api_definition in it
        # but the object needs to be just the API definition itself
        if isinstance(APIdefinition, str):
            # convert to a dict so we can test for the api_definition key
            APIdefinition = json.loads(APIdefinition)
        if 'api_definition' in APIdefinition:
            return APIdefinition['api_definition']
        return APIdefinition

    # Gateway __createAPI
    def __createAPI(self, APIdefinition):
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/tyk/apis', data=APIdefinition, headers=headers, verify=False)

    # Gateway createAPI
    def createAPI(self, APIdefinition):
        # need to convert it to a dict so we can check for api_definition and extract its contents
        APIdefinition = self.standardiseAPI(APIdefinition)
        response = self.__createAPI(json.dumps(APIdefinition))
        # automatically call the group reload (makes things simpler for a caller)
        self.reloadGroup()
        return response

    # Gateway createAPIs
    def createAPIs(self, APIdefinition, numberToCreate):
        APIdefinition = self.standardiseAPI(APIdefinition)
        APIName = APIdefinition['name']
        apis = self.getAPIs().json()
        # create a dictionary of all API names
        allnames = dict()
        for api in apis:
            allnames[api['name']] = 1
        i = 1
        numberCreated = 0
        while numberCreated < numberToCreate:
            # work out the next free name (format is name-i)
            while APIName+str(i) in allnames:
                i += 1
            newname=APIName+str(i)
            allnames[newname] = 1
            APIdefinition['api_id'] = newname
            APIdefinition['name'] = newname
            APIdefinition['slug'] = newname
            APIdefinition['proxy']['listen_path'] = '/'+newname+'/'
            print(f'Adding API {APIdefinition["name"]}, {APIdefinition["proxy"]["listen_path"]}')
            # create the API but don't reload the group
            response = self.__createAPI(json.dumps(APIdefinition))
            print(response.json())
            # if a call fails, stop and return the number of successes
            if response.status_code != 200:
                break
            numberCreated += 1
        # reload now
        self.reloadGroup()
        return numberCreated

    # TODO: test updateAPI
    # Gateway updateAPI
    def updateAPI(self, APIdefinition, APIid):
        if isinstance(APIdefinition, dict):
            APIdefinition = json.dumps(APIdefinition)
        headers = {'Authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        reponse =  requests.put(f'{self.URL}/tyk/apis/{APIid}', data=APIdefinition, headers=headers, verify=False)
        self.reloadGroup()
        return response

    # Gateway deleteAPI (private function which doesn't call reloadGroup)
    def __deleteAPI(self, APIid):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.delete(f'{self.URL}/tyk/apis/{APIid}', headers=headers, verify=False)

    # Gateway deleteAPI
    def deleteAPI(self, APIid):
        response = self.__deleteAPI(APIid)
        self.reloadGroup()
        return response

    # Gateway deleteAllAPIs
    def deleteAllAPIs(self):
        allDeleted = True
        apis = self.getAPIs().json()
        for api in apis:
            print(f'Deleting API: {api["name"]}: {api["api_id"]}')
            response = self.__deleteAPI(api['api_id'])
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        self.reloadGroup()
        return allDeleted


    # Gateway Policy functions

    # Gateway getPolicy
    def getPolicy(self, policyID):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/policies/{policyID}', headers=headers, verify=False)

    # Gateway getPolicies
    def getPolicies(self):
        headers = {'x-tyk-authorization' : self.authKey}
        response = requests.get(f'{self.URL}/tyk/policies', headers=headers, verify=False)
        body_json = {}
        body_json['policies'] = response.json()
        response._content = json.dumps(body_json).encode()
        return response

    # Gateway createPolicy
    def createPolicy(self, policyDefinition):
        if isinstance(policyDefinition, dict):
            if not 'id' in policyDefinition:
                policyDefinition['id'] = str(uuid.uuid4())
            policyDefinition = json.dumps(policyDefinition)
            print(policyDefinition)
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        response =  requests.post(f'{self.URL}/tyk/policies', data=policyDefinition, headers=headers, verify=False)
        return response

    # Gateway createPolicies
    def createPolicies(self, policyDefinition, APIid, numberToCreate):
        policies = self.getPolicies().json()
        # create a dictionary of all policy names
        PolicyName = policyDefinition['name']
        for policy in policies['policies']:
            allnames[policy['name']] = 1
        i = 1
        numberCreated = 0
        while numberCreated < numberToCreate:
            # work out the next free name (format is name-i)
            while PolicyName+str(i) in allnames:
                i += 1
            newname=PolicyName+str(i)
            allnames[newname] = 1
            policyDefinition['name']=PolicyName+str(i)
            policyDefinition['access_rights_array'] = json.loads('[{ "api_id": "' + APIid + '", "versions": [ "Default" ], "allowed_urls": [], "restricted_types": [], "limit": null, "allowance_scope": "" }]')
            print(f'Creating policy: {policyDefinition["name"]}')
            response = self.createPolicy(json.dumps(policyDefinition))
            print(response.json())
            # if a call fails, stop and return the number of successes
            if response.status_code != 200:
                break
            numberCreated += 1
        return numberCreated

    # Gateway updatePolicy
    def updatePolicy(self, policyDefinition, policyID):
        if isinstance(policyDefinition, dict):
            policyDefinition = json.dumps(policyDefinition)
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.put(f'{self.URL}/tyk/policies/{policyID}', data=policyDefinition, headers=headers, verify=False)

    # Gateway deletePolicy
    def deletePolicy(self, policyID):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.delete(f'{self.URL}/tyk/policies/{policyID}', headers=headers, verify=False)

    # Gateway deleteAllPolicies
    def deleteAllPolicies(self):
        allDeleted = True
        policies = self.getPolicies().json()
        for policy in policies['policies']:
            print(f'Deleting policy: {policy["_id"]}')
            response = self.deletePolicy(policy['_id'])
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted


    # Gateway Key functions

    # Gateway getKeys
    def getKeys(self):
        headers = {'x-tyk-authorization' : self.authKey}
        response = requests.get(f'{self.URL}/tyk/keys', headers=headers, verify=False)
        body_json = response.json()
        #print(json.dumps(body_json, indent=2))
        if response.status_code == 200:
            # pull the Keys out of the 'keys' array so that the format is the same as it is from the Dashboard
            keys = []
            for key in body_json['keys']:
                keys.append(key)
            response._content = json.dumps(keys).encode()
        return response

    # Dashboard getKeysDetailed
    def getKeysDetailed(self):
        headers = {'x-tyk-authorization' : self.authKey}
        response = requests.get(f'{self.URL}/tyk/keys', headers=headers, verify=False)
        body_json = response.json()
        print(json.dumps(body_json, indent=2))
        if response.status_code == 200:
            # pull the Keys out of the 'keys' array so that the format is the same as it is from the Dashboard
            keys = []
            for key in body_json['keys']:
                keyResp = self.getKey(key)
                if keyResp.status_code == 200:
                    #keyJSON = f'"{key}": "{keyResp.json()}"'
                    #keys.append(keyResp.json())
                    #keys.append(keyJSON)
                    body_json['keys'] = keyResp.json()
            print(json.dumps(body_json, indent=2))
            response._content = json.dumps(keys).encode()
        print(json.dumps(response.json()))
        return response

    # Gateway getKey
    def getKey(self, keyID):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/keys/{keyID}', headers=headers, verify=False)

    # Gateway createKey
    def createKey(self, keyDefinition):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/tyk/keys', data=keyDefinition, headers=headers, verify=False)

    # Gateway createCustomKey
    def createCustomKey(self, keyDefinition, keyID):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.post(f'{self.URL}/tyk/keys/{keyID}', data=keyDefinition, headers=headers, verify=False)

    # Gateway updateKey
    def updateKey(self, keyDefinition, keyID):
        if isinstance(keyDefinition, dict):
            keyDefinition = json.dumps(keyDefinition)
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.put(f'{self.URL}/tyk/keys/{keyID}', data=keyDefinition, headers=headers, verify=False)

    # Gateway deleteKey
    def deleteKey(self, keyID):
        headers = {'x-tyk-authorization' : self.authKey}
        headers['Content-Type'] = 'application/json'
        return requests.delete(f'{self.URL}/api/keys/{keyID}', headers=headers, verify=False)

    # Gateway deleteAllKeys
    def deleteAllKeys(self):
        allDeleted = True
        keys = self.getKeys().json()
        for key in keys['keys']:
            keyID = key['key_id']
            print(f'Deleting key: {keyID}')
            response = self.deleteKey(keyID)
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted

    # Gateway keyExists
    def keyExists(self, keyID):
        headers = {'x-tyk-authorization' : self.authKey}
        resp = requests.get(f'{self.URL}/tyk/keys/{keyID}', headers=headers, verify=False)
        return resp.status_code == 200


    # Gateway Certificate functions

    # Gateway getCerts
    def getCerts(self, orgid='*'):
        headers = {'x-tyk-authorization' : self.authKey}
        # I know that orgid is needed when the gateway is connected to the dashboard.
        # But I'm not sure about when it's in CE mode
        return requests.get(f'{self.URL}/tyk/certs?p=-1&org_id={orgid}', headers=headers, verify=False)

    # Gateway getCert
    def getCert(self, certid):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/certs/{certid}', headers=headers, verify=False)

    # Gateway getCertsDetails
    def getCertsDetails(self):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.get(f'{self.URL}/tyk/certs?p=-1&mode=detailed', headers=headers, verify=False)

    # Gateway createCert
    def createCert(self, certFile):
        headers = {'x-tyk-authorization' : self.authKey}
        files={'data': open(certFile,'r')}
        return requests.post(f'{self.URL}/tyk/certs', files=files, headers=headers, verify=False)

    # Gateway deleteCert
    def deleteCert(self, certid):
        headers = {'x-tyk-authorization' : self.authKey}
        return requests.delete(f'{self.URL}/tyk/certs/{certid}', headers=headers, verify=False)

    # Gateway deleteAllCerts
    def deleteAllCerts(self):
        allDeleted = True
        certs = self.getCerts().json()
        print(certs)
        for certid in certs['certs']:
            print(f'Deleting certificate: {certid}')
            response = self.deleteCert(certid)
            print(response.json())
            if response.status_code != 200:
                allDeleted = False
        return allDeleted

