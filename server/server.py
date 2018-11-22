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
from datetime import datetime
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

CONFIRM_ELECTION_START = "confirm_election_start"
CONFIRM_ELECTION_START_OK = "Ok"
CONFIRM_ELECTION_START_NO = "No"

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

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

    """
    A flag that the server that started the election progress sets to True. Consider a scenario: The leader has just 
    gone down and server 3 for instance has initated the leader decision. If almost directly after server 2 also gets a 
    request and sees that the leader is down, then this server will also try to imitate a leader decision. However 
    since server 3 has already stated the process we don't want server 2 to do it as well. So when the request comes to 
    server 3 it should see that this variable is true and send back a response that the process has already started. 
    Since this works like a lock, if a server crashes in the middle of the election process and can't pass the message 
    along the ring this value will never be false and we will not be able to select a new leader. Therefore, you need 
    to somehow release the "lock" after some time if the election process hasn't finished.
    """
    is_election_ongoing = False
    leader_election_init_timestamp = None

    # Leader info
    leader_number = 0
    leader_node = 0
    leader_ip = ""

    def initiate_leader_decision():
        # ------------------------------------------------------------------------------------------------------
        # INIT FUNCTIONS
        # ------------------------------------------------------------------------------------------------------
        global vessel_list, node_id, leader_node, leader_ip, is_election_ongoing

        try:
            time.sleep(1)

            is_election_ongoing = True

            is_successful_request = False

            next_node = START_NODE + 1

            while is_successful_request is False:

                if next_node > len(vessel_list):
                    next_node = 1

                if node_id == next_node:
                    leader_node, leader_ip = None, None
                    return

                next_vessel = vessel_list.get(next_node)

                data = {
                    'current_leader_node': node_id,
                    'current_leader_number': election_number
                }

                try:
                    res = requests.post('http://{}/leader/{}'.format(next_vessel, LEADER_DECIDE), headers=JSON_DATA_HEADER, json=data, timeout=10)

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
        global START_NODE, vessel_list, node_id, is_election_ongoing, leader_election_init_timestamp

        leader_election_init_timestamp = datetime.now()

        print "Timestamp:", leader_election_init_timestamp

        START_NODE = node_id
        data = {
            "timestamp": leader_election_init_timestamp.strftime(TIMESTAMP_FORMAT)
        }

        for vessel_id, vessel_ip in vessel_list.items():
            print "Type of:", type(vessel_id)
            if vessel_id != node_id:
                try:
                    res = requests.post("http://{}/leader/{}".format(vessel_ip, LEADER_REINITIATE),
                                        headers=JSON_DATA_HEADER, json=data).json()

                    if res[CONFIRM_ELECTION_START] == CONFIRM_ELECTION_START_NO:
                        leader_election_init_timestamp = None
                        return

                except requests.RequestException:
                    pass

        # The server that reaches this position will start the leader selection process. Send start node and mark for
        # other that a leader election is in progress
        data = {
            "start_node": START_NODE
        }
        propagate_to_vessels("/leader/{}".format(LEADER_REINITIATE), data, JSON_DATA_HEADER)

        leader_election_init_timestamp = None
        initiate_leader_decision()

    def begin_propagation(url, payload={}, headers={}):
        """
        Since we use propagate_to_vessels at many places, this method avoid some code duplication
        :param url: The url to call
        :param payload: What data to send
        :param headers: Extra header information, such as Content-type
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

            if node_id != leader_node:
                data_to_send = {
                    "entry": entry
                }
                # To see if leader is up or not
                requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_ADD),
                              headers=JSON_DATA_HEADER, json=data_to_send)
            else:
                board_actions(BOARD_ADD, entry=entry)

        except requests.RequestException:
            # Leader is not up
            if is_election_ongoing is False:
                # If two requests are made at the same time to restart leader election without starting another thread
                # the main thread will be busy waiting for the other servers to respond to the request to start the
                # leader election and the program will deadlock, at the moment, if server 1 sends a LEADER_REINITIATE
                # message and a client would try to add a message on server 2 and the client adds the message before
                # the LEADER_REINITATE has been recieved then they will cancel each other out
                # TODO - Add timestamps to determine who gets to start the leader election
                thread = Thread(target=_restart_leader_election)
                thread.daemon = True
                thread.start()

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):
        global board, node_id
        try:
            action_to_perform = request.forms.get("action")
            entry = request.forms.get("entry")

            if action_to_perform == "0":
                if node_id != leader_node:
                    data_to_send = {
                            "entry_sequence": element_id,
                            "entry": entry
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_MODIFY),
                                          headers=JSON_DATA_HEADER, json=data_to_send)
                else:
                    board_actions(BOARD_MODIFY, element_id, entry)
            else:
                if node_id != leader_node:
                    data_to_send = {
                        "entry_sequence": element_id
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_DELETE),
                                          headers=JSON_DATA_HEADER, json=data_to_send)
                else:
                    board_actions(BOARD_DELETE, requested_entry_sequence=element_id)

        except requests.RequestException:
            if not is_election_ongoing:
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
        This route handles requests/actions that concern the process of choosing the leader server.

        :param action: What action we should perform. They are the following:
            LEADER_CONFIRM: We have selected a new leader, confirm this and set information about the newly elected leader
            LEADER_REINITIATE: The previous leader is not responding therefore start over the election process
            LEADER_DECIDE: This action is performed during the electing process and sends a request to the next node in
                the circle algorithm.

        :return: Return a Http response with internal server error if there were an exception. A json object if the
            action was to reinitiate the election process otherwise a response with status code 200
        """
        global vessel_list, node_id, leader_node, leader_ip, START_NODE, leader_number, is_election_ongoing, leader_election_init_timestamp

        try:
            payload = request.json

            if action == LEADER_CONFIRM:
                # Send message to other vessels to confirm the leader
                leader_node = int(payload["leader_node"])
                leader_ip = payload["leader_ip"]
                leader_number = int(payload["leader_number"])

                is_election_ongoing = False

            elif action == LEADER_REINITIATE:
                if payload.get("start_node", None) is not None:
                    START_NODE = int(payload["start_node"])
                    is_election_ongoing = True
                    return HTTPResponse(status=OK)

                received_timestamp = payload["timestamp"]

                if is_election_ongoing is False:

                    # If timestamp is not none then it means that this server has also tried to initiate a leader
                    # election. Therefore, compare timestamps to determine who will continue
                    if leader_election_init_timestamp is not None:
                        # We favour the server that initiated the call first
                        if leader_election_init_timestamp > datetime.strptime(received_timestamp, TIMESTAMP_FORMAT):
                            return HTTPResponse(
                                status=OK,
                                headers=JSON_DATA_HEADER,
                                body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_OK})
                            )
                        else:
                            return HTTPResponse(
                                status=OK,
                                headers=JSON_DATA_HEADER,
                                body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_NO})
                            )
                    else:
                        return HTTPResponse(
                            status=OK,
                            headers=JSON_DATA_HEADER,
                            body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_OK})
                        )

                else:
                    return HTTPResponse(
                        status=OK,
                        headers=JSON_DATA_HEADER,
                        body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_NO})
                    )

            else:
                current_leader_node = int(payload["current_leader_node"])
                current_leader_number = int(payload["current_leader_number"])

                print "START_NODE,", START_NODE

                # We have visited all vessels, propagate message to other servers that they should confirm leader node
                if node_id == START_NODE:

                    # Indicate that the election process is over
                    is_election_ongoing = False

                    leader_ip = vessel_list[current_leader_node]
                    leader_node = current_leader_node
                    leader_number = current_leader_number

                    data = {
                        "leader_node": leader_node,
                        "leader_ip": leader_ip,
                        "leader_number": leader_number
                    }

                    begin_propagation("/leader/{}".format(LEADER_CONFIRM), payload=data, headers=JSON_DATA_HEADER)

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
                                next_node += 1

                        except requests.RequestException:
                            # Some type of connection error occurred while trying to connect to the server. We can check
                            # for more specific types but at the moment, keep it like this
                            next_node += 1

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

        try:
            data = request.json

            board_actions(action, data.get("entry_sequence"), data.get("entry"))

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR


    def board_actions(action, requested_entry_sequence=None, entry=None):
        global entry_sequence

        if action == BOARD_ADD:
            add_new_element_to_store(entry_sequence, entry)
            begin_propagation("/propagate/{}".format(BOARD_ADD),
                              payload={"entry_sequence": entry_sequence, "entry": entry}, headers=JSON_DATA_HEADER)
            entry_sequence += 1
        elif action == BOARD_MODIFY:
            modify_element_in_store(requested_entry_sequence, entry)
            begin_propagation("/propagate/{}".format(BOARD_MODIFY),
                              payload={"entry_sequence": requested_entry_sequence, "entry": entry}, headers=JSON_DATA_HEADER)
        else:
            delete_element_from_store(requested_entry_sequence)
            begin_propagation("/propagate/{}".format(BOARD_DELETE), payload={"entry_sequence": requested_entry_sequence},
                              headers=JSON_DATA_HEADER)

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