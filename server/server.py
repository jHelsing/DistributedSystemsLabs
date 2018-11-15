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
from threading import Thread

from bottle import Bottle, run, request, template, response
import requests

BOARD_ADD = 'Add'
BOARD_DELETE = 'Delete'
BOARD_MODIFY = 'Modify'

OK = 200
BAD_REQUEST = 400
INTERNAL_SERVER_ERROR = 500

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Dictionary to hold the entries to the board
    board = {}
    # Each entry in the dictionary gets an entry
    entry_number = 1

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # Should nopt be given to the student
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id, entry_number
        success = False
        try:
            # If a propagated call arrives after we have added an entry directly, then we don't want to override the
            # already present item in the board. Therefore, increase the sequence number until there is no entry
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
                _begin_propagation(BOARD_ADD, entry_number, entry)
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
                    _begin_propagation(BOARD_MODIFY, element_id, entry)
                    response.status = OK
            # Delete
            else:
                if delete_element_from_store(element_id):
                    # Start new thread to propagate
                    _begin_propagation(BOARD_DELETE, element_id)
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

    def _begin_propagation(action, entry_number, entry=None):
        """
        Since there are muliple places where we want to start a new
        thread, just extract that functionality here to avoid duplication
        """
        thread = Thread(target=propagate_to_vessels, args=("/propagate/{}/{}".format(action, entry_number), entry))
        thread.daemon = True
        thread.start()

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