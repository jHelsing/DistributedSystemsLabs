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

BOARD_ADD = 'Add'
BOARD_DELETE = 'Delete'
BOARD_MODIFY = 'Modify'

OK = 200
BAD_REQUEST = 400
INTERNAL_SERVER_ERROR = 500

START_NODE = 1

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Dictionary to represent the board
    board = {}
    # Each entry gets a sequence number
    entry_number = 1

    leader_number = random.randint(0, 1000)
    leader_node = 0

    def decide_leader():
        """
        A method that initiates the leader decision conversation
        """
        global vessel_list, node_id

        try:
            # So that all servers start
            time.sleep(2)
            # This node starts the conversation starts the conversation"
            if node_id == START_NODE:
                # Acquire IP address of next vessel
                next_vessel = get_next_ip(vessel_list, str(int(node_id)+1))
                data_to_send = {
                    "current_leader_node": node_id,
                    "current_leader_number": leader_number
                }
                # Make initial request
                requests.post('http://{}/leader/decide'.format(next_vessel), data=data_to_send)

        except Exception as e:
            print e

    def get_next_ip(vessel_list, next_node_id):
        try:
            if vessel_list.get(next_node_id, None) is None:
                next_node_id = "1"
            return vessel_list[next_node_id]
        except Exception as e:
            print e

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # Should nopt be given to the student
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id, entry_number
        success = False
        try:

            # If the sequence numbers are not synced between servers we need to make sure that we don't override an entry
            while board.get(entry_sequence) is not None:
                entry_sequence += 1

            board[entry_sequence] = element
            # Sync the global variable where we added the latest entry
            entry_number = entry_sequence
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
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
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

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    def _begin_propagation(url, entry=None):
        """
        Since there are muliple places where we want to start a new
        thread, just extract that functionality here to avoid duplication
        """
        thread = Thread(target=propagate_to_vessels, args=(url, entry))
        thread.daemon = True
        thread.start()


    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id
        # Sort dictionary when sending it, since when looping through a dictionary the order is not preserved
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)), members_name_string='Anton Solback')

    @app.get('/board')
    def get_board():
        global board, node_id
        # Sort dictionary when sending it, since when looping through a dictionary the order is not preserved
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        '''
        Adds a new element to the board
        Called directly when a user is doing a POST request on /board
        '''
        global board, node_id, entry_number
        try:
            entry = request.forms.get('entry')
            # Set the default response status
            response.status = BAD_REQUEST

            if add_new_element_to_store(entry_number, entry):
                # Start new thread to propagate
                _begin_propagation("/propagate/{}/{}".format(BOARD_ADD, entry_number), entry)
                entry_number += 1
                # We successfully added an item, change response code
                response.status = OK

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        # Receives an action to perform on the board
        try:
            action_to_perform = request.forms.get('action')
            entry = request.forms.get("entry")
            # Set the default response status
            response.status = BAD_REQUEST

            # Modify
            if action_to_perform == "0":
                if modify_element_in_store(element_id, entry):
                    # Start new thread to propagate
                    _begin_propagation("/propagate/{}/{}".format(BOARD_MODIFY, element_id), entry)
                    response.status = OK
            # Delete
            else:
                if delete_element_from_store(element_id):
                    # Start new thread to propagate
                    _begin_propagation("/propagate/{}/{}".format(BOARD_DELETE, element_id))
                    response.status = OK

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>/<element_id:int>')
    def propagation_received(action, element_id):
        global entry_number

        try:
            entry = request.body.getvalue()
            # Set the default response status
            response.status = BAD_REQUEST

            # If the acton was successful then set the response code to indicate this. Applies for all actions
            if action == BOARD_ADD:
                if add_new_element_to_store(element_id, entry, True):
                    entry_number += 1
                    response.status = OK

            elif action == BOARD_DELETE:
                if delete_element_from_store(element_id, True):
                    response.status = OK

            else:
                if modify_element_in_store(element_id, request.body.getvalue(), True):
                    response.status = OK

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

        return response

    @app.post('/leader/decide')
    def leader_decision():
        """
        Route used to decide who the leader is
        :return:
        """
        global vessel_list, node_id, leader_node

        try:
            current_leader_node = request.forms.get("current_leader_node")
            current_leader_number = request.forms.get("current_leader_number")

            if node_id == START_NODE:
                _begin_propagation("/leader/confirm", {"leader_node":current_leader_node})
                leader_node = current_leader_node
                response = OK
            else:
                # Send message to next vessel
                next_vessel = get_next_ip(vessel_list, str(int(node_id)+1))

                if leader_number > current_leader_number:
                    current_leader_node = node_id
                    current_leader_number = leader_number

                data_to_send = {
                    "current_leader_node": current_leader_node,
                    "current_leader_number": current_leader_number
                }
                # Make new request
                requests.post('http://{}/leader/decide'.format(next_vessel), data=data_to_send)

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/leader/confirm')
    def leader_confirm():
        """
        Used to confirm the leader to all the other nodes
        :return:
        """
        try:
            data = request.forms.get("leader_node")
            print "Leader node is:", data

        except Exception as e:
            print e
            response.status = INTERNAL_SERVER_ERROR

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