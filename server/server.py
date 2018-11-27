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

# ----------------------------------CONSTANTS------------------------------------------
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
# -------------------------------END CONSTANTS------------------------------------------

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Dictionary to represent the board
    board = {}

    # Each entry gets a sequence number
    entry_sequence = 1

    # Every node's start number in the election process
    election_number = random.randint(0, 1000)

    # To indicate that a leader election is currently ongoing
    is_election_ongoing = False

    # If two requests are made at the same time to start a new leader election, we need to know who made the request
    # first so that one can continue
    leader_election_init_timestamp = None

    # Leader info
    leader_number = 0
    leader_node = 0
    leader_ip = ""

    # ------------------------------------------------------------------------------------------------------
    # UTILS
    # ------------------------------------------------------------------------------------------------------
    def initiate_leader_decision():
        """
        This function starts a new leader election. This just serves as an entry point to start the conversation
        The election algorithm the ring election and has a cost of 2n where n is the number of servers.
        """

        global vessel_list, node_id, leader_node, leader_ip, is_election_ongoing

        try:

            time.sleep(10)

            is_election_ongoing = True

            # To keep track of when we were able to contact the next server in the ring.
            is_successful_request = False

            # To get the IP address of the next server in the list
            next_node = START_NODE + 1

            # What to do while unable to contact next server
            while is_successful_request is False:

                # We have 8 servers, if we start at server 6 and need to visit all servers we need to check when we have
                # reached the end of the dictionary
                if next_node > len(vessel_list):
                    next_node = 1

                # If no other servers are contactable set leader_node to self and leader_ip to none
                if node_id == next_node:
                    leader_node, leader_ip = node_id, None
                    return

                # Get ip of next server
                next_vessel = vessel_list.get(next_node)

                # Data to send along.
                data = {
                    'current_leader_node': node_id,
                    'current_leader_number': election_number
                }

                try:
                    # Make request to server
                    res = requests.post('http://{}/leader/{}'.format(next_vessel, LEADER_DECIDE), headers=JSON_DATA_HEADER, json=data)

                    # Handle response code
                    if res.status_code == OK:
                        # Exit from the while loop
                        is_successful_request = True
                    else:
                        # We raise an exception here because we want to have the same error handling
                        raise requests.RequestException

                except requests.RequestException:
                    # There was a error in trying to connect to the server. Move to next server
                    next_node += 1

        except Exception as e:
            print e

    def restart_leader_election():
        """
        If the leader goes down we need to elect a new leader. This method takes care of restarting the election
        """
        global START_NODE, vessel_list, node_id, leader_election_init_timestamp

        # If there are two requests at the same time, before we can set is_election_ongoing to True, then we need to
        # decide who should start a new leader election.
        leader_election_init_timestamp = datetime.now()

        # Convert datetime object to string and send it
        data = {
            "timestamp": leader_election_init_timestamp.strftime(TIMESTAMP_FORMAT)
        }

        # Contact all other servers except self and say that: "I want to reinitiate a leader election. Is that OK?"
        for vessel_id, vessel_ip in vessel_list.items():
            if vessel_id != node_id:
                try:
                    # Get the response
                    res = requests.post("http://{}/leader/{}".format(vessel_ip, LEADER_REINITIATE),
                                        headers=JSON_DATA_HEADER, json=data).json()

                    # Handle response
                    if res[CONFIRM_ELECTION_START] == CONFIRM_ELECTION_START_NO:
                        # If one server for some reason don't agree that this server should be able to start a leader
                        # election, reset timestamp and return
                        leader_election_init_timestamp = None
                        return

                except requests.RequestException:
                    # If a server isn't
                    pass

        # The server that reaches this position will start the leader selection process. Send start node and mark for
        # other that a leader election is in progress
        START_NODE = node_id
        data = {
            "start_node": START_NODE
        }

        propagate_to_vessels("/leader/{}".format(LEADER_REINITIATE), data, JSON_DATA_HEADER)

        leader_election_init_timestamp = None

        # We have now decided who starts will start the leader election. Start it.
        initiate_leader_decision()

    def begin_propagation(url, payload=None, headers=None):
        """
        Since we use propagate_to_vessels at many places, this method avoid some code duplication because of the thread logic
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
        """
        Adds a new entry to the board. If the node is not the leader, then send a request to the leader with a message
        that we want to add a new item to the board. If the leader is down then we first check if there is an election
        in progress and that's the case then just return. Otherwise try to start a new leader election
        """
        global board, node_id, entry_sequence, vessel_list, START_NODE

        try:
            entry = request.forms.get('entry')

            if node_id != leader_node:
                data_to_send = {
                    "entry": entry
                }
                # Try to send message to leader
                requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_ADD),
                              headers=JSON_DATA_HEADER, json=data_to_send)
            else:
                # Add entry to own board
                board_actions(BOARD_ADD, entry=entry)

        except requests.RequestException:
            # Leader is not up, check if election is already in progress
            if is_election_ongoing is False:
                # Election is not in progress. Try to start a new election process. We need to start a new thread here
                # since if we can start a new election we need to listen to /leader/decide when we have gone a full lap
                # in the circle algorithm and if two start at the same time, we need to compare timestamps
                thread = Thread(target=restart_leader_election)
                thread.daemon = True
                thread.start()

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):
        """
        A route that handles modifications and deletions on the board
        :param element_id: The id which to perform the action on.
        """
        global board, node_id
        try:
            action_to_perform = request.forms.get("action")
            entry = request.forms.get("entry")

            # Modify
            if action_to_perform == "0":
                if node_id != leader_node:
                    # Send request to leader
                    data_to_send = {
                            "entry_sequence": element_id,
                            "entry": entry
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_MODIFY),
                                          headers=JSON_DATA_HEADER, json=data_to_send)
                else:
                    # Modify item directly to the board if it's the leader server
                    board_actions(BOARD_MODIFY, element_id, entry)
            else:
                if node_id != leader_node:
                    # Send request to leader
                    data_to_send = {
                        "entry_sequence": element_id
                    }
                    requests.post("http://{}/askleader/{}".format(leader_ip, BOARD_DELETE),
                                          headers=JSON_DATA_HEADER, json=data_to_send)
                else:
                    # Delete item directly to the board if it's the leader server
                    board_actions(BOARD_DELETE, requested_entry_sequence=element_id)

        except requests.RequestException:
            # Leader can't be contacted
            if not is_election_ongoing:
                # There is no election already in progress. Try to start a new one
                restart_leader_election()
        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>')
    def propagation_received(action):
        """
        Leader has propagated an action to other servers
        :param action: What action to take
        :return:
        """
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

            # A new leader has been selected, confirm this.
            if action == LEADER_CONFIRM:
                # We receive information about new leader.
                leader_node = int(payload["leader_node"])
                leader_ip = payload["leader_ip"]
                leader_number = int(payload["leader_number"])

                # Indicate that the election process is over
                print "Server nr:", leader_node, "is the leader"
                is_election_ongoing = False

            # The leader has gone down an a server wants to reinitate the leader election
            elif action == LEADER_REINITIATE:
                # A server will only send a request with a json object containing start_node if that server has been
                # chosen to start the new election process
                if payload.get("start_node", None) is not None:
                    # Reset START_NODE so that all know when to stop
                    START_NODE = int(payload["start_node"])
                    is_election_ongoing = True
                    return HTTPResponse(status=OK)

                # The timestamp of the server that has tried to start a new election
                received_timestamp = payload["timestamp"]

                # If an election has already started then just return
                if is_election_ongoing is False:

                    # If the local timestamp variable is not None it means that this server has also tried to start a
                    # new election process
                    if leader_election_init_timestamp is not None:

                        # Favour the server who requested to start the election process first
                        if leader_election_init_timestamp > datetime.strptime(received_timestamp, TIMESTAMP_FORMAT):
                            # Our timestamp is higher than the server that has sent this request to us. Therefore, we
                            # send back a message that it's OK from our side that "you" start the process
                            return HTTPResponse(
                                status=OK,
                                headers=JSON_DATA_HEADER,
                                body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_OK})
                            )
                        else:
                            # We requested to start a new election process first. Therefore, deny the requesting server
                            return HTTPResponse(
                                status=OK,
                                headers=JSON_DATA_HEADER,
                                body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_NO})
                            )
                    else:
                        # We have not tried to initiate a new election process. Therefore, send OK back to requesting
                        # server
                        return HTTPResponse(
                            status=OK,
                            headers=JSON_DATA_HEADER,
                            body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_OK})
                        )

                else:
                    # An election process is in progress. Deny requesting server
                    return HTTPResponse(
                        status=OK,
                        headers=JSON_DATA_HEADER,
                        body=json.dumps({CONFIRM_ELECTION_START: CONFIRM_ELECTION_START_NO})
                    )

            else:
                # An election process has started and we are the next server in the ring. Check who the current leader
                # is and what their number is
                current_leader_node = int(payload["current_leader_node"])
                current_leader_number = int(payload["current_leader_number"])

                print "START_NODE,", START_NODE

                # We have visited all servers, propagate message to other servers that they should confirm leader node
                if node_id == START_NODE:

                    # Indicate that the election process is over
                    is_election_ongoing = False

                    # Set information about new leader and send to other servers
                    leader_ip = vessel_list[current_leader_node]
                    leader_node = current_leader_node
                    leader_number = current_leader_number

                    data = {
                        "leader_node": leader_node,
                        "leader_ip": leader_ip,
                        "leader_number": leader_number
                    }

                    print "Server nr:", leader_node, "is the leader"

                    begin_propagation("/leader/{}".format(LEADER_CONFIRM), payload=data, headers=JSON_DATA_HEADER)

                else:
                    if election_number > current_leader_number:
                        new_leader_node = node_id
                        new_leader_number = election_number

                        payload = {
                            "current_leader_node": new_leader_node,
                            "current_leader_number": new_leader_number
                        }

                    # Try to send message to next server in the ring
                    is_successful_request = False

                    next_node = node_id + 1

                    while is_successful_request is False:

                        # We have reached the end of the dictionary start from the beginning
                        if next_node > len(vessel_list):
                            next_node = 1

                        next_vessel = vessel_list.get(next_node)
                        # In order to get to this point we had to make one initial request so we will eventually make a
                        # request to the one that initiated the conversation, i.e., node_id == START_NODE
                        print "Contacting server:", next_node
                        try:
                            res = requests.post('http://{}/leader/{}'.format(next_vessel, LEADER_DECIDE),
                                                headers=JSON_DATA_HEADER, json=payload)
                            # We were able to contact a server

                            if res.status_code == OK:
                                is_successful_request = True
                            else:
                                # We raise an exception here because we want to have the same error handling
                                raise requests.RequestException

                        except requests.RequestException:
                            print "Can't contact server:", next_node
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
    @app.post('/askleader/<action>')
    def ask_leader(action):
        """
        A route that servers use when they want to ask the leader something
        :param action: What action to take. These are:
            BOARD_ADD: Add an item to the board
            BOARD_MODIFY: Modify an item on the board
            BOARD_DELETE: Delete an item from the board
        """
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