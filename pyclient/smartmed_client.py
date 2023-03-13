# Copyright 2018 Intel Corporation
#
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
smartmedClient class interfaces with Sawtooth through the REST API.
It accepts input from a client CLI/GUI/BUI or other interface.
'''
# developed by MH

from builtins import BaseException
import hashlib
import base64
import random
import time
import requests
import yaml

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

# The Transaction Family Name
FAMILY_NAME = 'smartmed'
# TF Prefix is first 6 characters of SHA-512("smartmed"), a4d219

def _hash(data):
    return hashlib.sha512(data).hexdigest()

class smartmedClient(object):
    '''Client smartmed class

    Supports "register", "request", "find", "list", "delete", and "interested" functions.
    '''

    def __init__(self, base_url, key_file=None):
        '''Initialize the client class.

           This is mainly getting the key pair and computing the address.
        '''
        self._base_url = base_url

        if key_file is None:
            self._signer = None
            return

        try:
            with open(key_file) as key_fd:
                private_key_str = key_fd.read().strip()
        except OSError as err:
            raise Exception(
                'Failed to read private key {}: {}'.format(
                    key_file, str(err)))

        try:
            private_key = Secp256k1PrivateKey.from_hex(private_key_str)
        except ParseError as err:
            raise Exception( \
                'Failed to load private key: {}'.format(str(err)))

        self._signer = CryptoFactory(create_context('secp256k1')) \
            .new_signer(private_key)
        self._public_key = self._signer.get_public_key().as_hex()

        # Address is 6-char TF prefix + hash of "mysmartmed"'s public key

    def _get_prefix(self):
        return _hash(FAMILY_NAME.encode('utf-8'))[0:6]

    def _get_DS_address(self, id, ds):
        return self._get_prefix() + \
            _hash(id.encode('utf-8'))[0:32] + \
                _hash(ds.encode('utf-8'))[0:32]

        # Address is 6-char TF prefix + hash of userid + hash of psid    
    def _get_address(self, id):
        return self._get_prefix() + \
            _hash(id.encode('utf-8'))[0:64] 

    # For each CLI command, add a method to:
    # 1. Do any additional handling, if required
    # 2. Create a transaction and a batch
    # 2. Send to REST API

    def register(self, projectID, feasibility, ethicality, approved_time, validity_duration,
    legal_base, DS_selection_criteria, project_issuer):
        '''register projects in the ledger.'''
        return self._wrap_and_send("register", projectID, feasibility, ethicality, approved_time, validity_duration, 
        legal_base, DS_selection_criteria, project_issuer, wait=10)

    def request(self, projectID, username):
        '''request a project from the ledger.'''
        return self._wrap_and_send("request", projectID, username, None, None, None, None, None, None, wait=10)

    def reply(self, projectID, username, consent):
        '''replying to consent.'''
        return self._wrap_and_send("reply", projectID, username, consent, None, None, None, None, None, wait=10)

    def find(self, color, qid):
        '''find associated DSs with the color tag.'''
        return self._wrap_and_send("find", color, qid, None, None, None, None, None, None, wait=10)

    def delete(self, projectID):
        '''delete a registered query.'''
        return self._wrap_and_send("delete", None, projectID, None, None, None, None, None, None, wait=10)

    def get_query(self, qid):
        '''Get a query registered in the ledger by its ID'''
        address = self._get_address(str(qid))
        result = self._send_to_rest_api("state/{}".format(address))
        try:
            return base64.b64decode(yaml.safe_load(result)["data"])
        except BaseException:
            return None    

    def interested(self, username, qid, status, ds1, ds2, ds3, ds4, ds5):
        '''submit if the associated DS is interested in the query or not.'''
        return self._wrap_and_send("interested", username, qid, status, ds1, ds2, ds3, ds4, ds5, wait=10)    

    def list(self):
        addr_prefix = self._get_prefix()

        result = self._send_to_rest_api(
            "state?address={}".format(addr_prefix))

        try:
            encoded_entries = yaml.safe_load(result)["data"]

            return [
                base64.b64decode(entry["data"]) for entry in encoded_entries
            ]

        except BaseException:
            return None

    def showDS(self, projectID, ds):
        addr_ds = self._get_DS_address(projectID, ds)

        result = self._send_to_rest_api(
            "state?address={}".format(addr_ds))

        try:
            encoded_entries = yaml.safe_load(result)["data"]

            return [
                base64.b64decode(entry["data"]) for entry in encoded_entries
            ]

        except BaseException:
            return None             

    def _send_to_rest_api(self, suffix, data=None, content_type=None):
        '''Send a REST command to the Validator via the REST API.

           Called by list() &  _wrap_and_send().
           The latter caller is made on the behalf of register(), request(), reply(), and delete() .
        '''
        url = "{}/{}".format(self._base_url, suffix)
        print("URL to send to REST API is {}".format(url))

        headers = {}

        if content_type is not None:
            headers['Content-Type'] = content_type

        try:
            if data is not None:
                result = requests.post(url, headers=headers, data=data)
            else:
                result = requests.get(url, headers=headers)

            if not result.ok:
                raise Exception("Error {}: {}".format(
                    result.status_code, result.reason))
        except requests.ConnectionError as err:
            raise Exception(
                'Failed to connect to {}: {}'.format(url, str(err)))
        except BaseException as err:
            raise Exception(err)

        return result.text

    def _wait_for_status(self, batch_id, wait, result):
        '''Wait until transaction status is not PENDING (COMMITTED or error).

           'wait' is time to wait for status, in seconds.
        '''
        if wait and wait > 0:
            waited = 0
            start_time = time.time()
            while waited < wait:
                result = self._send_to_rest_api("batch_statuses?id={}&wait={}"
                                               .format(batch_id, wait))
                status = yaml.safe_load(result)['data'][0]['status']
                waited = time.time() - start_time

                if status != 'PENDING':
                    return result
            return "Transaction timed out after waiting {} seconds." \
               .format(wait)
        else:
            return result


    def _wrap_and_send(self, action, amount, qid, status, ds1, ds2, ds3, ds4, ds5, wait=None):
        '''Create a transaction, then wrap it in a batch.

           Even single transactions must be wrapped into a batch.
           Called by register(), find(), interested(), and delete(). 
        '''

        # Generate a CSV UTF-8 encoded string as the payload.
        if action == "register":
            raw_payload = ",".join([action, amount, qid, status, ds1, ds2, ds3, ds4, ds5])
            address = self._get_address(amount)
        elif action == "request":
            raw_payload = ",".join([action, amount, qid])
            address = self._get_address(str(amount))
        elif action == "reply":
            raw_payload = ",".join([action, amount, qid, status])
            address = self._get_DS_address(amount, qid)
            print('reply cl add: ', address)        
        elif action == "find":
            raw_payload = ",".join([action, amount, str(qid)])
            address = self._get_address(str(qid))
        elif action == "interested":    
            raw_payload = ",".join([action, amount, str(qid), status, ds1, ds2, ds3, ds4, ds5])
            address = self._get_address(str(qid))
        elif action == "delete":    
            raw_payload = ",".join([action, str(qid)])
            address = self._get_address(str(qid))           
        payload = raw_payload.encode() # Convert Unicode to bytes

        # Construct the address where we'll store our state.
        # We just have one input and output address (the same one).        

        # Create a TransactionHeader.
        header = TransactionHeader(
            signer_public_key=self._public_key,
            family_name=FAMILY_NAME,
            family_version="1.0",
            inputs=[address],
            outputs=[address],
            dependencies=[],
            payload_sha512=_hash(payload),
            batcher_public_key=self._public_key,
            nonce=random.random().hex().encode()
        ).SerializeToString()

        # Create a Transaction from the header and payload above.
        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=self._signer.sign(header)
        )

        transaction_list = [transaction]

        # Create a BatchHeader from transaction_list above.
        header = BatchHeader(
            signer_public_key=self._public_key,
            transaction_ids=[txn.header_signature for txn in transaction_list]
        ).SerializeToString()

        # Create Batch using the BatchHeader and transaction_list above.
        batch = Batch(
            header=header,
            transactions=transaction_list,
            header_signature=self._signer.sign(header))

        # Create a Batch List from Batch above
        batch_list = BatchList(batches=[batch])
        batch_id = batch_list.batches[0].header_signature

        # Send batch_list to the REST API
        result = self._send_to_rest_api("batches",
                                       batch_list.SerializeToString(),
                                       'application/octet-stream')

        # Wait until transaction status is COMMITTED, error, or timed out
        return self._wait_for_status(batch_id, wait, result)

