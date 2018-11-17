# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: Anton Solback
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse
import operator
import random
from threading import Thread
from bottle import Bottle, run, request, template, response, HTTPResponse
import requests

BOARD_ADD = 'add'
BOARD_DELETE = 'delete'
BOARD_MODIFY = 'modify'

OK = 200
BAD_REQUEST = 400
INTERNAL_SERVER_ERROR = 500

JSON_DATA_HEADER = {'content-type':'application/json'}

START_NODE = 4
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Dictionary to represent the board
    board = {}
    # Each entry gets a sequence number
    entry_sequence = 1

    leader_number = random.randint(0, 1000)
    leader_node = 0
    leader_ip = ""

    def decide_leader():
        # ------------------------------------------------------------------------------------------------------
        # INIT FUNCTIONS
        # ------------------------------------------------------------------------------------------------------
        global vessel_list, node_id

        try:
            # This node starts the conversation starts the conversation"
            time.sleep(1)
            if node_id == START_NODE:
                # Acquire IP address of next vessel
                next_vessel = get_next_ip(str(int(node_id)+1))
                data = {'current_leader_node': node_id,
                        'current_leader_number': leader_number
                }
                # Make initial request
                requests.post('http://{}/leader/decide'.format(next_vessel),
                              headers=JSON_DATA_HEADER, data=json.dumps(data))

        except Exception as e:
            print e

    def get_next_ip(next_node_id):
        global vessel_list

        try:
            if vessel_list.get(next_node_id, None) is None:
                next_node_id = "1"
            return vessel_list[next_node_id]
        except Exception as e:
            print e

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id
        success = False
        try:
            board[entry_sequence] = element
            success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            board[entry_sequence] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            del board[entry_sequence]
            success = True
        except Exception as e:
            print e
        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # should be given to the students?
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload, req = 'POST', headers=None):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), headers=headers, data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, headers=None, req = 'POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req=req, headers=headers)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    def _begin_propagation(url, payload=None, headers=None):
        """
        Since there are muliple places where we want to start a new
        thread, just extract that functionality here to avoid duplication
        """
        thread = Thread(target=propagate_to_vessels, args=(url, payload, headers))
        thread.daemon = True
        thread.start()


    # ------------------------------------------------------------------------------------------------------
    # ROUTESw
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id, leader_node

        try:
            return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                            board_dict=sorted(board.items(), key=operator.itemgetter(0)), members_name_string='Anton Solback')
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.get('/board')
    def get_board():
        global board, node_id

        try:
            return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                            board_dict=sorted(board.items(), key=operator.itemgetter(0)))
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        global board, node_id, entry_sequence, vessel_list

        try:
            entry = request.forms.get('entry')
            # Leader should only talk to other servers
            if node_id != leader_node:
                data_to_send = json.dumps({
                    "entry": entry
                })
                requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_ADD),
                              headers=JSON_DATA_HEADER, data=data_to_send)

            response.status = 200

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, node_id
        try:
            action_to_perform = request.forms.get("action")
            entry = request.forms.get("entry")

            response.status = BAD_REQUEST

            if node_id != leader_node:
                if action_to_perform == "0":
                    data_to_send = json.dumps({
                            "entry_sequence": element_id,
                            "entry": entry
                    })
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_MODIFY),
                                          headers=JSON_DATA_HEADER, data=data_to_send)
                else:
                    data_to_send = json.dumps({
                        "entry_sequence": element_id
                    })
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_DELETE),
                                          headers=JSON_DATA_HEADER, data=data_to_send)

            response.status = 200

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>')
    def propagation_received(action):
        global entry_sequence, board, node_id, leader_node

        try:
            data = request.json

            if action == BOARD_ADD:
                add_new_element_to_store(data["entry_sequence"], data["entry"], True)

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

        return response

    @app.post('/leader/<action>')
    def leader_decision(action):
        """
        Route used to decide who the leader is
        :return:
        """
        global vessel_list, node_id, leader_node, leader_ip

        try:
            payload = request.json

            if action == "confirm":
                leader_node = payload["leader_node"]
                leader_ip = payload["leader_ip"]
                print "Leader node:", leader_node
            else:
                current_leader_node = payload["current_leader_node"]
                current_leader_number = payload["current_leader_number"]

                if node_id == START_NODE:
                    leader_ip = vessel_list[str(current_leader_node)]
                    leader_node = current_leader_node
                    # We have visited all vessels, propagate message to other servers that they should confirm leader node
                    _begin_propagation("/leader/confirm", json.dumps({"leader_node":leader_node, "leader_ip": leader_ip}),
                                       headers=JSON_DATA_HEADER)
                else:
                    # Send message to next vessel
                    next_vessel = get_next_ip(str(int(node_id)+1))

                    if leader_number > int(current_leader_number):
                        new_leader_node = node_id
                        new_leader_number = leader_number

                        payload = {
                            "current_leader_node": new_leader_node,
                            "current_leader_number": new_leader_number
                        }

                    requests.post('http://{}/leader/decide'.format(next_vessel),
                                  headers=JSON_DATA_HEADER, data=json.dumps(payload))
            response.status = 200

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR
    # ------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------
    # LEADER ACTIONS
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for postGive it to the students-----------------------------------------------------------------------------------------------------
    # Execute the code
    @app.post('/askleader/<action>')
    def ask_leader(action):
        global entry_sequence

        try:
            data = request.json

            if action == BOARD_ADD:
                add_new_element_to_store(entry_sequence, data["entry"])
                payload = {
                    "entry_sequence": entry_sequence,
                    "entry": data["entry"]
                }
                _begin_propagation("/propagate/{}".format(BOARD_ADD), json.dumps(payload), JSON_DATA_HEADER)
                entry_sequence += 1

            elif action == BOARD_MODIFY:
                modify_element_in_store(int(data["entry_sequence"]), data["entry"])
            else:
                delete_element_from_store(data["entry_sequence"])

            response.status = OK

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for postGive it to the students-----------------------------------------------------------------------------------------------------
    # Execute the code
    def main():
        global vessel_list, node_id, app

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

        try:
            if node_id == START_NODE:
                thread = Thread(target=decide_leader)
                thread.daemon = True
                thread.start()
            run(app, host=vessel_list[str(node_id)], port=port)

        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)