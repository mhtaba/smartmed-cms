#!/usr/bin/env python3

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
Command line interface for smartmed TF.
Parses command line arguments and passes to the smartmedClient class
to process.
'''

import argparse
from datetime import date
import logging
import os
import sys

import traceback
import random
import time
import datetime
from multiprocessing import Process

from colorlog import ColoredFormatter
from smartmed_client import smartmedClient

KEY_NAME = 'mysmartmed'

out_time = datetime.datetime.now()

# hard-coded for simplicity (otherwise get the URL from the args in main):
DEFAULT_URL = 'http://localhost:8008'
# For Docker:
# DEFAULT_URL = 'http://rest-api:8008'

def create_console_handler(verbose_level):
    '''Setup console logging.'''
    del verbose_level # unused
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)
    clog.setLevel(logging.DEBUG)
    return clog

def setup_loggers(verbose_level):
    '''Setup logging.'''
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))

def create_parser(prog_name):
    '''Create the command line argument parser for the smartmed CLI.'''
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)

    parser = argparse.ArgumentParser(
        description='Provides subcommands to manage your queries',
        parents=[parent_parser])

    subparsers = parser.add_subparsers(title='subcommands', dest='command')
    subparsers.required = True

    register_subparser = subparsers.add_parser('register',
                                           help='populate the ledger with project ID and instances',
                                           parents=[parent_parser])                                           
    register_subparser.add_argument('projectID',
                                type=str,
                                help='the project ID has such a template: PR12345678')
    register_subparser.add_argument('--feasibility',
                               type=str,
                               help='is the project feasible? (true/false)')
    register_subparser.add_argument('--ethicality',
                               type=str,
                               help='is the project ethical? (true/false)')
    register_subparser.add_argument('--approved_time',
                               type=str,
                               help='when the project is approved: dd.mm.yyyy')
    register_subparser.add_argument('--validity_duration',
                               type=str,
                               help='one month after the approved time: dd.mm.yyyy')
    register_subparser.add_argument('--legal_base',
                               type=str,
                               help='consent:1, performance of a contract:2, legitimate interest:3, vital interest:4, legal requirement:5, public interest:6')                                                                                                            
    register_subparser.add_argument('--DS_selection_criteria',
                               type=str,
                               help='one of these three options: red, green, blue')
    register_subparser.add_argument('--project_issuer',
                               type=str,
                               help='username of the project issuer')

    request_subparser = subparsers.add_parser('request',
                                           help='ask to run a registered project by giving the projectID',
                                           parents=[parent_parser])                                           
    request_subparser.add_argument('projectID',
                                type=str,
                                help='the project ID has such a template: PR12345678')
    request_subparser.add_argument('--username',
                               type=str,
                               help='username of the project requester which has to be same as the project issuer')                                                                                  

    reply_subparser = subparsers.add_parser('reply',
                                           help='replying to consent',
                                           parents=[parent_parser])                                           
    reply_subparser.add_argument('projectID',
                                type=str,
                                help='the project ID has such a template: PR12345678')
    reply_subparser.add_argument('--username',
                               type=str,
                               help='username of the DS')
    reply_subparser.add_argument('consent',
                               type=str,
                               help='yes/no')

    find_subparser = subparsers.add_parser('find',
                                           help='find the list of DSs with color tag',
                                           parents=[parent_parser])                                           
    find_subparser.add_argument('color',
                                type=str,
                                help='the color to be found')
    find_subparser.add_argument('--qid',
                               type=int,
                               help='query id of the request')
    list_subparser = subparsers.add_parser('list',
                                           help='display all of the query results',
                                           parents=[parent_parser])
    showDS_subparser = subparsers.add_parser('showDS',
                                           help='display the consent status of a given DS for a given project',
                                           parents=[parent_parser])
    showDS_subparser.add_argument('projectID',
                                type=str,
                                help='the project ID has such a template: PR12345678')                                       

    showDS_subparser.add_argument('DS',
                                type=str,
                                help='the ds has such a template: DS12345678')

    showPR_subparser = subparsers.add_parser('showPR',
                                           help='display the consent status of a given project',
                                           parents=[parent_parser])
    showPR_subparser.add_argument('projectID',
                                type=str,
                                help='the project ID has such a template: PR12345678')                                                                   

    interested_subparser = subparsers.add_parser('interested',
                                           help='The DS shows its interest to the query',
                                           parents=[parent_parser])
    interested_subparser.add_argument('--username',
                                type=str,
                                help='the ID of the DS that is going to answer the query')
    interested_subparser.add_argument('--qid',
                                type=int,
                                help='the ID of the query needed to be answered')
    interested_subparser.add_argument('status',
                                type=str,
                                help='yes/no response from the DS')
    
    auto_subparser = subparsers.add_parser('auto_run',
                                           help='To help run the system automatically',
                                           parents=[parent_parser])
    interested_subparser.add_argument('--incoming_tps',
                                type=int,
                                help='the throughput of incoming transactions')
    

    delete_subparser = subparsers.add_parser('delete',
                                          help='delete a registered project',
                                          parents=[parent_parser])
    delete_subparser.add_argument('projectID',
                               type=str,
                               help='Project ID of the one that is going to be deleted')
    file_subparser = subparsers.add_parser('file',help='Swithching to the file execution mode', parents=[parent_parser])
    file_subparser.add_argument('filepath',
                               type=str,
                               help='Path to the file to be executed')

    return parser

def _get_private_keyfile(key_name):
    '''Get the private key for key_name.'''
    home = os.path.expanduser("~")
    key_dir = os.path.join(home, ".sawtooth", "keys")
    return '{}/{}.priv'.format(key_dir, key_name)

def do_register(args):
    '''Subcommand to populate the ledger with the projects. Calls client class to do the registering.'''
    privkeyfile = _get_private_keyfile(args.project_issuer)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    response = client.register(args.projectID, args.feasibility, args.ethicality, args.approved_time, args.validity_duration,
    args.legal_base, args.DS_selection_criteria, args.project_issuer)
    print("Find Response: {}".format(response))
#    out_throughput()

def do_request(args):
    '''Subcommand to request a project based on projectID. Calls client class to do the requesting.'''
    privkeyfile = _get_private_keyfile(args.username)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    response = client.request(args.projectID, args.username)
    print("Find Response: {}".format(response))

def do_reply(args):
    '''Subcommand to replying to consent. Calls client class to do the replying.'''
    privkeyfile = _get_private_keyfile(args.username)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    response = client.reply(args.projectID, args.username, args.consent)
    print("Find Response: {}".format(response))            

def do_find(args):
    '''Subcommand to find a list of DSs with associated color. Calls client class to do the finding.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    response = client.find(args.color,args.qid)
    print("Find Response: {}".format(response))

def do_interested(args):
    '''Subcommand to show the interest of the DS to a query. Calls client class to do the interest.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    data = client.get_query(args.qid)
    if data is not None:
        qid, ds1, ds2, ds3, ds4, ds5 = data.decode().split(",")
    response = client.interested(args.username,args.qid,args.status,ds1,ds2,ds3,ds4,ds5)
    print("Find Response: {}".format(response))    

def do_list():
    '''Subcommand to show the list of query results.  Calls client class to do the showing.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    query_list = [
        tx.split(',')
        for txs in client.list()
        for tx in txs.decode().split('|')
    ]
    if query_list is not None:
        count = 0;
        for tx_data in query_list:
            count = count + 1
    #        qid, ds1, ds2, ds3, ds4, ds5 = tx_data
            projectID,feasibility,ethicality,approved_time,validity_duration,legal_base, \
                DS_selection_criteria,project_issuer,HD_trasfer_proof,*consent_reply = tx_data
            print(count, ") Project ID:"+ projectID, \
                "| Feasibility:"+ feasibility, \
                "| Ethicality:"+ ethicality, \
                "| Approved time:"+ approved_time, \
                "| Validity duration:"+ validity_duration, \
                "| Legal base:"+ legal_base, \
                "| DS selection criteria:"+ DS_selection_criteria, \
                "| Project issuer:"+ project_issuer, \
                "| HD transfer proof:"+ HD_trasfer_proof, \
                "| Consent reply:"+ str(consent_reply)     )
    else:
        raise Exception("Transaction data not found")

def do_showDS(args):
    '''Subcommand to show the status of the given DS for a given project. Calls client class to do the showing.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    query_list = [
        tx.split(',')
        for txs in client.showDS(args.projectID, args.DS)
        for tx in txs.decode().split('|')
    ]
    if query_list is not None:
    #    count = 0;
        for tx_data in query_list:
    #        count = count + 1
    #        qid, ds1, ds2, ds3, ds4, ds5 = tx_data
            projectID, DS, consent_reply = tx_data
            print("Project ID:"+ projectID, \
                "| DS:"+ DS, \
                "| Consent reply:"+ consent_reply)
    else:
        raise Exception("Transaction data not found")

def do_showPR(args):
    '''Subcommand to show the consent status of the given project. Calls client class to do the showing.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    query_list = [
        tx.split(',')
        for txs in client.showPR(args.projectID)
        for tx in txs.decode().split('|')
    ]
    if query_list is not None:
        for tx_data in query_list:
            projectID, DS, consent_reply = tx_data
            print("Project ID:"+ projectID, \
                "| DS:"+ DS, \
                "| Consent reply:"+ consent_reply)
    else:
        raise Exception("Transaction data not found")                              

def do_delete(args):
    '''Subcommand to delete a query.  Calls client class to do the deleting.'''
    privkeyfile = _get_private_keyfile(KEY_NAME)
    client = smartmedClient(base_url=DEFAULT_URL, key_file=privkeyfile)
    response = client.delete(args.projectID)
    print("delete Response: {}".format(response))

def read_from_file(args):
    command_file = open(args.filepath, 'r')
    while True:
        # Get next line from file
        line = command_file.readline()
        if not line:
            break
        line_args = line.split()
        parser = create_parser(os.path.basename(sys.argv[0]))
        line_args = parser.parse_args(line_args)
        function_dispatcher(line_args)
    command_file.close()

def auto_run():
    micro_conversion = 1000000
    time_interval = 1.0 / 10 * micro_conversion
    print("interval is:" + str(time_interval))
    processes = []
    x = 1
    args_list = ["register","--feasibility true --ethicality true --approved_time 03.11.2022 --validity_duration 03.12.2022 --legal_base 1 --DS_selection_criteria GREEN --project_issuer salar1"]
    while True:
        start_time = datetime.datetime.now()
        proj_id = []
        for i in range(0,10):
            proj_id.append(str(random.randint(0, 9)))
        arg = args_list[0] + " " + "PR" + ''.join(proj_id) + " " + args_list[1]
        line_args = arg.split()
        parser = create_parser(os.path.basename(sys.argv[0]))
        line_args = parser.parse_args(line_args)

        #function_dispatcher(line_args)
        processes.append(Process(target=function_dispatcher, args=(line_args,)))
        processes[-1].start()

        end_time = datetime.datetime.now()
        time_difference = end_time - start_time
        print(time_difference.microseconds)
        if(time_interval < time_difference.microseconds):
            while True:
                print("Incoming Throughput could not be reached!")
                print(x)
            break
        print("time differene is (microSecs):")
        print(time_interval - time_difference.microseconds)

        print(x)
        x = x+1

        time.sleep((time_interval - time_difference.microseconds)/micro_conversion)

def out_throughput():
    global out_time
    time = datetime.datetime.now()
    delta = time - out_time
    out_time = time
    print("Time interval between two commited transactions are:")
    print(delta.seconds)
    print("Equivalent to: " + str(1.0/delta.seconds) + " TPS")
    

def function_dispatcher(args):
    if args.command == 'register':
        do_register(args)
    elif args.command == 'request':
        do_request(args)
    elif args.command == 'reply':
        do_reply(args)        
    elif args.command == 'find':
        do_find(args)
    elif args.command == 'interested':
        do_interested(args)
    elif args.command == 'delete':
        do_delete(args)        
    elif args.command == 'list':
        do_list()
    elif args.command == 'showDS':
        do_showDS(args)
    elif args.command == 'showPR':
        do_showPR(args)        
    elif args.command == 'auto_run':
        auto_run()
    elif args.command == 'file':
        read_from_file(args)                   	
    else:
        raise Exception("Invalid command: {}".format(args.command))


def main(prog_name=os.path.basename(sys.argv[0]), args=None):
    '''Entry point function for the client CLI.'''
    try:
        if args is None:
            args = sys.argv[1:]
        parser = create_parser(prog_name)
        args = parser.parse_args(args)
        verbose_level = 0
        setup_loggers(verbose_level=verbose_level)
        function_dispatcher(args)

    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

