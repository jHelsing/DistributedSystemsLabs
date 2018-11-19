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

LEADER_CONFIRM = "confirm"
LEADER_REINITIATE = "reinitiate"
LEADER_DECIDE = "decide"

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

    # Every node's start number in the election process
    election_number = random.randint(0, 1000)

    # Leader info
    leader_number = 0
    leader_node = 0
    leader_ip = ""

    def initiate_leader_decision():
        # ------------------------------------------------------------------------------------------------------
        # INIT FUNCTIONS
        # ------------------------------------------------------------------------------------------------------
        global vessel_list, node_id, leader_node, leader_ip

        try:
            # Wait until servers has started
            time.sleep(1)

            is_successful_request = False
            next_node = START_NODE + 1

            while is_successful_request is False:

                # We have reached the end of the dictionary start from the beginning
                if next_node > len(vessel_list):
                    next_node = 1

                # No other server is reachable
                if node_id == next_node:
                    # We have tried to contact all other vessels and no one is alive
                    leader_node, leader_ip = None, None
                    return

                next_vessel = vessel_list.get(next_node)

                # We send our information
                data = {
                    'current_leader_node': node_id,
                    'current_leader_number': election_number
                }

                try:
                    res = requests.post('http://{}/leader/{}'.format(next_vessel, LEADER_DECIDE), headers=JSON_DATA_HEADER, json=data)

                    # We were able to contact a server
                    if res.status_code == OK:
                        is_successful_request = True
                    else:
                        # TODO - What to do if status_code is Internal Server Error
                        pass

                except requests.RequestException:
                    next_node += 1

        except Exception as e:
            print e

    # ------------------------------------------------------------------------------------------------------
    # UTILS
    # ------------------------------------------------------------------------------------------------------

    def _restart_leader_election():
        global START_NODE
        """
        Leader can't be contacted, therefore try to select a new leader.
        1. Set START_NODE to your own node_id so we now when we need to stop.
        2. Send updated START_NODE to other vessel. This is because the previous start_node need to know
        that we are starting from another node so that we can go a full circle in the leader election

        First solution:
        Since this node initiated the leader decision, it needs to know when we have visited all other nodes.
        Currently, the way this is done is that it listens for /leader/decide and if node_if is START_NODE
        then we have gone through all nodes and can decide who will be the next leader and send this to all
        other vessels. Since we need to listen on that endpoint we need to start the leader_decision in
        another thread. The downside is that we don't now here who the new leader is so we can't add the new
        entry in the board. We can't add to ours either since then it won't be synced with the others. A
        solution would be to send back a message to the client and ask them to re-enter the message.
        """
        START_NODE = node_id
        data = {
            "start_node": START_NODE
        }
        propagate_to_vessels("/leader/{}".format(LEADER_REINITIATE), payload=data, headers=JSON_DATA_HEADER)

        thread = Thread(target=initiate_leader_decision)
        thread.daemon = True
        thread.start()

    def _begin_propagation(url, payload={}, headers={}):
        """
        Since there are muliple places where we want to start a new
        thread, just extract that functionality here to avoid duplication
        """
        thread = Thread(target=propagate_to_vessels, args=(url, payload, headers))
        thread.daemon = True
        thread.start()

    # ------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        """
        If the call is propagated then you should be allowed to override entries since the leader decides the final
        position. We just want to add an item to the board so the user can see it and then when we receive the leaders
        propagation message we override our current order. Otherwise we have to wait for the leader to receive the
        message, que it and then propagate it to everyone and then you will be able to see it.
        """
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
            if board.get(entry_sequence) is not None:
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
    def contact_vessel(vessel_ip, path, payload, headers, req = 'POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                data_type = headers.get("content-type")
                if data_type == "application/json":
                    res = requests.post('http://{}{}'.format(vessel_ip, path), headers=headers, json=payload)
                else:
                    res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        # Vessel is down, do nothing, just pass to return False
        except requests.RequestException:
            pass
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, headers=None, req = 'POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, headers, req=req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id, leader_node

        try:
            return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                            board_dict=sorted(board.items(), key=operator.itemgetter(0)), members_name_string='Anton Solback',
                            leader_node=leader_node, leader_number=leader_number)
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.get('/board')
    def get_board():
        global board, node_id

        try:
            return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                            board_dict=sorted(board.items(), key=operator.itemgetter(0)), leader_node=leader_node,
                            leader_number=leader_number)
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        global board, node_id, entry_sequence, vessel_list, START_NODE

        try:
            entry = request.forms.get('entry')

            # Leader should only talk to other servers
            if node_id != leader_node:
                data_to_send = {
                    "entry": entry
                }
                # To see if leader is up or not
                requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_ADD),
                              headers=JSON_DATA_HEADER, json=data_to_send)

        except requests.RequestException:
            # Leader is not up
            _restart_leader_election()
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):
        global board, node_id
        try:
            action_to_perform = request.forms.get("action")
            entry = request.forms.get("entry")

            response.status = BAD_REQUEST

            if node_id != leader_node:
                if action_to_perform == "0":
                    data_to_send = {
                            "entry_sequence": element_id,
                            "entry": entry
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_MODIFY),
                                          headers=JSON_DATA_HEADER, json=data_to_send)
                else:
                    data_to_send = {
                        "entry_sequence": element_id
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_DELETE),
                                          headers=JSON_DATA_HEADER, json=data_to_send)

        except requests.RequestException:
            # Leader is not up
            _restart_leader_election()
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>')
    def propagation_received(action):
        global entry_sequence, board, node_id, leader_node

        try:
            data = request.json

            if action == BOARD_ADD:
                entry_sequence = int(data["entry_sequence"])
                add_new_element_to_store(entry_sequence, data["entry"], True)
            elif action == BOARD_MODIFY:
                modify_element_in_store(int(data["entry_sequence"]), data["entry"], True)
            else:
                delete_element_from_store(int(data["entry_sequence"]), True)

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
        global vessel_list, node_id, leader_node, leader_ip, START_NODE, leader_number

        try:
            payload = request.json

            if action == LEADER_CONFIRM:
                # Send message to other vessels to confirm the leader
                leader_node = int(payload["leader_node"])
                leader_ip = payload["leader_ip"]
                leader_number = int(payload["leader_number"])

                print "Leader is node:", leader_node
            elif action == LEADER_REINITIATE:
                START_NODE = int(payload["start_node"])
            else:
                current_leader_node = int(payload["current_leader_node"])
                current_leader_number = int(payload["current_leader_number"])

                if node_id == START_NODE:
                    leader_ip = vessel_list[current_leader_node]
                    leader_node = current_leader_node
                    leader_number = current_leader_number
                    # We have visited all vessels, propagate message to other servers that they should confirm leader node
                    data = {
                        "leader_node":leader_node,
                        "leader_ip": leader_ip,
                        "leader_number": leader_number
                    }
                    _begin_propagation("/leader/{}".format(LEADER_CONFIRM), payload=data, headers=JSON_DATA_HEADER)
                else:
                    if election_number > current_leader_number:
                        new_leader_node = node_id
                        new_leader_number = election_number

                        payload = {
                            "current_leader_node": new_leader_node,
                            "current_leader_number": new_leader_number
                        }

                    is_successful_request = False
                    next_node = node_id + 1

                    while is_successful_request is False:

                        # We have reached the end of the dictionary start from the beginning
                        if next_node > len(vessel_list):
                            next_node = 1

                        next_vessel = vessel_list.get(next_node)
                        # In order to get to this point we had to make one initial request so we will eventually make a
                        # request to the one that initiated the conversation, i.e., node_id == START_NODE
                        try:
                            res = requests.post('http://{}/leader/{}'.format(next_vessel, LEADER_DECIDE),
                                                headers=JSON_DATA_HEADER, json=payload)
                            # We were able to contact a server
                            if res.status_code == OK:
                                is_successful_request = True
                            else:
                                # TODO - What to do if status_code is Internal Server Error?
                                pass

                        except requests.RequestException:
                            # Vessel is not running. Remove from vessel list?
                            next_node += 1

            return HTTPResponse(status=OK)

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
                data = {
                    "entry_sequence": entry_sequence,
                    "entry": data["entry"]
                }
                _begin_propagation("/propagate/{}".format(BOARD_ADD), payload=data, headers=JSON_DATA_HEADER)
                entry_sequence += 1

            elif action == BOARD_MODIFY:
                modify_element_in_store(int(data["entry_sequence"]), data["entry"])
                _begin_propagation("/propagate/{}".format(BOARD_MODIFY), payload=data, headers=JSON_DATA_HEADER)
            else:
                delete_element_from_store(int(data["entry_sequence"]))
                _begin_propagation("/propagate/{}".format(BOARD_DELETE), payload=data, headers=JSON_DATA_HEADER)

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
            vessel_list[i] = '10.1.0.{}'.format(str(i))

        try:
            if node_id == START_NODE:
                thread = Thread(target=initiate_leader_decision)
                thread.daemon = True
                thread.start()
            run(app, host=vessel_list[node_id], port=port)

        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)