#!/usr/bin/env python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
'''
smartmedTransactionHandler class interfaces for smartmed Transaction Family.
'''

import traceback
import sys
import hashlib
import logging
import random
import string
import os.path

from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.processor.core import TransactionProcessor

# hard-coded for simplicity (otherwise get the URL from the args in main):
DEFAULT_URL = 'tcp://localhost:4004'
# For Docker:
#DEFAULT_URL = 'tcp://validator:4004'
 
LOGGER = logging.getLogger(__name__)

FAMILY_NAME = "smartmed"
# TF Prefix is first 6 characters of SHA-512("smartmed"), a4d219

def _hash(data):
    '''Compute the SHA-512 hash and return the result as hex characters.'''
    return hashlib.sha512(data).hexdigest()

def _get_smartmed_address(from_key,projID):
    '''
    Return the address of a smartmed object from the smartmed TF.

    The address is the first 6 hex characters from the hash SHA-512(TF name),
    plus the result of the hash SHA-512(smartmed public key).
    '''
    return _hash(FAMILY_NAME.encode('utf-8'))[0:6] + \
                 _hash(projID.encode('utf-8'))[0:64]


class smartmedTransactionHandler(TransactionHandler):
    '''
    Transaction Processor class for the smartmed Transaction Family.

    This TP communicates with the Validator using the accept/get/set functions
    This implements functions to "find".
    '''
    def __init__(self, namespace_prefix):
        '''Initialize the transaction handler class.

           This is setting the "smartmed" TF namespace prefix.
        '''
        self._namespace_prefix = namespace_prefix

    @property
    def family_name(self):
        '''Return Transaction Family name string.'''
        return FAMILY_NAME

    @property
    def family_versions(self):
        '''Return Transaction Family version string.'''
        return ['1.0']

    @property
    def namespaces(self):
        '''Return Transaction Family namespace 6-character prefix.'''
        return [self._namespace_prefix]

    def apply(self, transaction, context):
        '''This implements the apply function for the TransactionHandler class.

           The apply function does most of the work for this class by
           processing a transaction for the smartmed transaction family.
        '''

        # Get the payload and extract the smartmed-specific information.
        # It has already been converted from Base64, but needs deserializing.
        # It was serialized with CSV: action, value
        header = transaction.header
        payload_list = transaction.payload.decode().split(",")
        action = payload_list[0]
        if action == "register":
            projectID = payload_list[1]
            feasibility = payload_list[2]
            ethicality = payload_list[3]
            approved_time = payload_list[4]
            validity_duration = payload_list[5]
            legal_base = payload_list[6]
            DS_selection_criteria = payload_list[7]
            project_issuer = payload_list[8]
        elif action == "request":
            projectID = payload_list[1]
            username = payload_list[2]     
        elif action == "find":
            amount = payload_list[1]
            qid = payload_list[2]
        elif action == "interested":
            username = payload_list[1]
            qid = payload_list[2]
            status = payload_list[3]
            ds1 = payload_list[4]
            ds2 = payload_list[5]
            ds3 = payload_list[6]
            ds4 = payload_list[7]
            ds5 = payload_list[8]
        elif action == "delete":
            projectID = payload_list[1]

        # Get the signer's public key, sent in the header from the client.
        from_key = header.signer_public_key

        # Perform the action.
        if action == "register":
            LOGGER.info("ProjectID = %s.", projectID)   
            LOGGER.info("feasibility = %s.", feasibility)
            LOGGER.info("ethicality = %s.", ethicality)
            LOGGER.info("approved time= %s.", approved_time)
            LOGGER.info("validity duration = %s.", validity_duration)
            LOGGER.info("legal base = %s.", legal_base)
            LOGGER.info("DS selection criteria = %s.", DS_selection_criteria)
            LOGGER.info("project issuer = %s.", project_issuer)
            self._make_register(context, projectID, feasibility, ethicality, approved_time, validity_duration,
            legal_base, DS_selection_criteria, project_issuer, from_key)
        elif action == "request":
            LOGGER.info("ProjectID = %s.", projectID)   
            LOGGER.info("username = %s.", username)
            self._make_request(context, projectID, username, from_key)    
        elif action == "find":
            LOGGER.info("Amount = %s.", amount)   
            LOGGER.info("Query ID = %s.", qid)
            self._make_find(context, amount, qid, from_key)
        elif action == "interested":
            LOGGER.info("Username = %s.", username)        
            LOGGER.info("Query ID = %s.", qid)
            LOGGER.info("status = %s.", status)
            LOGGER.info("ds1 = %s.", ds1)
            LOGGER.info("ds2 = %s.", ds2)
            LOGGER.info("ds3 = %s.", ds3)
            LOGGER.info("ds4 = %s.", ds4)
            LOGGER.info("ds5 = %s.", ds5)
            self._make_interested(context, username, qid, status, ds1, ds2, ds3, ds4, ds5, from_key)            
        elif action == "delete":
            LOGGER.info("Query ID = %s.", projectID)
            self._make_delete(context, projectID, from_key)
        else:
            LOGGER.info("Unhandled action. Action should be bake or eat")

    @classmethod
    def _make_register(cls, context, projectID, feasibility, ethicality, approved_time, validity_duration,
            legal_base, DS_selection_criteria, project_issuer, from_key):
        '''populate the ledger with project ID and instances.'''
        project_address = _get_smartmed_address(from_key,projectID)
        LOGGER.info('Got the key %s and the project address %s.',
                    from_key, project_address)
        if legal_base == "1":
            legal_base = "consent"
        elif legal_base == "2":
            legal_base = "performance of interest"
        elif legal_base == "3":
            legal_base = "legitimate interest"
        elif legal_base == "4":
            legal_base = "vital interest"
        elif legal_base == "5":
            legal_base = "legal reguirement"
        elif legal_base == "6":
            legal_base = "public interest"                         
        project = [projectID,feasibility,ethicality,approved_time,validity_duration,legal_base,
        DS_selection_criteria,project_issuer,"n/a",{}]
        state_data = str(project).encode('utf-8')
        addresses = context.set_state({project_address: state_data})

    @classmethod
    def _make_request(cls, context, projectID, username, from_key):
        '''find associated DSs to the project.'''
        query_address = _get_smartmed_address(from_key,projectID)
        LOGGER.info('Got the key %s and the query address %s.',
                    from_key, query_address)
        state_entries = context.get_state([query_address])
        projectID,feasibility,ethicality,approved_time,validity_duration,legal_base, \
        DS_selection_criteria,project_issuer,HD_transfer_proof,consent_reply \
             = state_entries[0].data.decode().split(',')
        LOGGER.info("project issuer = %s.", project_issuer.replace("'","").strip())    
        if username == project_issuer.replace("'","").strip():
            consent_reply = []
            fr = open("./dslist.txt","r")
            lines = fr.readlines()
            for line in lines:
                data = line.strip().split(",")
                if data[1].casefold() == DS_selection_criteria.replace("'","").strip():
                    consent_reply.append(data[1])
            query_result = projectID,feasibility,ethicality,approved_time,validity_duration,legal_base, \
                DS_selection_criteria,project_issuer,HD_transfer_proof,consent_reply
            state_data = str(query_result).encode('utf-8')
            addresses = context.set_state({query_address: state_data})
        else:
            raise InternalError("Username Error")

        if len(addresses) < 1:
            raise InternalError("State Error")    


    @classmethod
    def _make_find(cls, context, amount, qid, from_key):
        '''find associated dsc from a specific dc based on the color tag.'''
        query_address = _get_smartmed_address(from_key,qid)
        LOGGER.info('Got the key %s and the query address %s.',
                    from_key, query_address)
        query_result = [qid,"n/a","n/a","n/a","n/a","n/a"]
        fr = open("./pyprocessor/dslist.txt","r")
        fw = open("./pyprocessor/ds-color.txt","w")
        lines = fr.readlines()
        for line in lines:
            data = line.strip().split(",")
            if data[2].casefold() == amount:
                if data[1] == "DS1Pubkey":
                    query_result[1] = "waiting"                   
                if data[1] == "DS2Pubkey":
                    query_result[2] = "waiting"
                if data[1] == "DS3Pubkey":
                    query_result[3] = "waiting"
                if data[1] == "DS4Pubkey":
                    query_result[4] = "waiting"
                if data[1] == "DS5Pubkey":
                    query_result[5] = "waiting"            
        fw.write(data[1])
        fw.write("\n")               
        fr.close()
        fw.close()
        state_data = str(query_result).encode('utf-8')
        addresses = context.set_state({query_address: state_data})

    def _make_interested(cls, context, username, qid, status, ds1, ds2, ds3, ds4, ds5, from_key):
        '''Register the interest of a DS to a query.'''
        query_address = _get_smartmed_address(from_key,qid)
        LOGGER.info('Got the key %s and the smartmed address %s.',
                    from_key, query_address)
        state_entries = context.get_state([query_address])
        qid, ds1, ds2, ds3, ds4, ds5 = state_entries[0].data.decode().split(',')        
        if status == "yes":
            status = "inetersted"
        else:
            status = "not interested"    
        if username == "ds1":
            query_result = qid, status, ds2, ds3, ds4, ds5
        if username == "ds2":
            query_result = qid, ds1, status, ds3, ds4, ds5
        if username == "ds3":
            query_result = qid, ds1, ds2, status, ds4, ds5
        if username == "ds4":
            query_result = qid, ds1, ds2, ds3, status, ds5
        if username == "ds5":
            query_result = qid, ds1, ds2, ds3, ds4, status                
        state_data = str(query_result).encode('utf-8')
        addresses = context.set_state({query_address: state_data})

        if len(addresses) < 1:
            raise InternalError("State Error")
        context.add_event(
            event_type="smartmed/bake",
            attributes=[("cookies-baked", username)])    

    @classmethod
    def _make_delete(cls, context, projectID, from_key):
        query_address = _get_smartmed_address(from_key,projectID)
        LOGGER.info('Got the key %s and the query address %s.',
                    from_key, query_address)
        context.delete_state([query_address])    

def main():
    '''Entry-point function for the smartmed Transaction Processor.'''
    try:
        # Setup logging for this class.
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)

        # Register the Transaction Handler and start it.
        processor = TransactionProcessor(url=DEFAULT_URL)
        sw_namespace = _hash(FAMILY_NAME.encode('utf-8'))[0:6]
        handler = smartmedTransactionHandler(sw_namespace)
        processor.add_handler(handler)
        processor.start()
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
