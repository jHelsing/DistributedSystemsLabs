# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 3
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
from threading import Thread

from bottle import Bottle, run, request, template, response
import requests

BOARD_ADD = 'add'
BOARD_DELETE = 'delete'
BOARD_MODIFY = 'modify'

TIMESTAMP_KEY = 'timestamp'
ENTRY_KEY = 'entry'

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

JSON_DATA_HEADER = {'content-type':'application/json'}

OK = 200
INTERNAL_SERVER_ERROR = 500

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Dictionary to represent the board
    """
    board: {
        entry_sequence: {
            timestamp: datetime.datetime
            entry: string
        }
    }
    """

    board = {}
    # Each entry gets a sequence number
    entry_sequence = -1

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # Should nopt be given to the student
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_data, is_propagated_call=False):
        global board, node_id, entry_sequence
        success = False
        found_correct_placement = False

        entry_sequence += 1
        try:
            # Convert received timestamp and convert it so that we can compare it
            received_timestamp = datetime.strptime(entry_data[TIMESTAMP_KEY], TIMESTAMP_FORMAT)
            received_entry = entry_data[ENTRY_KEY]

            if is_propagated_call:
                new_board = {}

                # Find position where we want to add entry
                for indexCounter, (timestamp, entry) in enumerate(board.values()):
                    timestamp = board[indexCounter][timestamp]
                    entry = board[indexCounter][entry]

                    if found_correct_placement:
                        new_board[indexCounter+1] = {}
                        new_board[indexCounter+1].update({
                            TIMESTAMP_KEY: timestamp,
                            ENTRY_KEY: entry
                        })
                        continue

                    new_board[indexCounter] = {}

                    if timestamp < received_timestamp:
                        new_board[indexCounter].update({
                            TIMESTAMP_KEY: timestamp,
                            ENTRY_KEY: entry
                        })
                    elif timestamp > received_timestamp:
                        new_board[indexCounter].update({
                            TIMESTAMP_KEY: received_timestamp,
                            ENTRY_KEY: received_entry
                        })

                        new_board[indexCounter + 1] = {}
                        new_board[indexCounter + 1].update({
                            TIMESTAMP_KEY: timestamp,
                            ENTRY_KEY: entry
                        })

                        # We have found the correct placement. Now we need to push back all resuming entries one step
                        found_correct_placement = True
                    else:
                        pass

                # The entry should be added to the back of the board
                if found_correct_placement is False:
                    new_board[entry_sequence] = {}

                    new_board[entry_sequence].update({
                        TIMESTAMP_KEY: received_timestamp,
                        ENTRY_KEY: received_entry
                    })

                board = new_board
            else:
                # When we add to our own board we just add it to the current value of the the entry_sequence counter.
                # When we get a propagated call we will have to decide the correct order of messages
                board[entry_sequence] = {}

                board[entry_sequence].update({
                    TIMESTAMP_KEY: received_timestamp,
                    ENTRY_KEY: received_entry
                })

            success = True
        except Exception as e:
            print "Exception occurred at add"
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False
        try:

            if is_propagated_call:
                pass
            else:
                board[entry_sequence][ENTRY_KEY] = modified_element

            success = True
        except Exception as e:
            print "Exception occurred at modify."
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            # Remove item from board
            if is_propagated_call:
                pass
            else:
                del board[entry_sequence]
            success = True
        except Exception as e:
            print "Exception occurred at delete."
            print e
        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # should be given to the students?
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload, headers, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                data_type = headers.get("content-type")
                if data_type == "application/json":
                    res = requests.post('http://{}{}'.format(vessel_ip, path), headers=headers, json=payload)
                else:
                    res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            else:
                res = requests.get('http://{}{}'.format(vessel_ip, path))

            if res.status_code == 200:
                success = True
        # Vessel is down, do nothing, just pass to return False
        except requests.RequestException:
            pass
        except Exception as e:
            print "Exception occurred at contact vessels"
            print e

        return success

    def propagate_to_vessels(path, payload=None, headers=None, req='POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if vessel_id != node_id:  # don't propagate to yourself
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
        global board, node_id
        try:
            # Sort dictionary on the entry_number in the dictionary
            return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)), members_name_string='Anton Solback')
        except Exception as e:
            print "Exception occurred at /."
            print e

    @app.get('/board')
    def get_board():
        global board, node_id
        try:
            # Sort dictionary on the entry_number in the dictionary
            return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)))
        except Exception as e:
            print "Exception occurred at /board (get)."
            print e
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        '''
        Adds a new element to the board
        Called directly when a user is doing a POST request on /board
        '''
        global board, node_id, entry_sequence
        try:
            entry = request.forms.get('entry')

            # Entry timestamp
            timestamp = datetime.now()

            # There is no reason why it wouldn't add the entry to the dictionary
            entry_data = {
                TIMESTAMP_KEY: timestamp.strftime(TIMESTAMP_FORMAT),
                ENTRY_KEY: entry
            }

            add_new_element_to_store(entry_data)
            # If we added it to our own board we need to tell others about it
            begin_propagation("/propagate/{}".format(BOARD_ADD), entry_data, JSON_DATA_HEADER)
            # Increment sequence number next time we want to add something
            # We successfully added an item, change response code

        except Exception as e:
            print "Exception occurred at /board (post)."
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        # Receives an action to perform on the board
        try:
            action_to_perform = request.forms.get('action')
            entry = request.forms.get("entry")

            # Modify
            if action_to_perform == "0":
                # If modification was successful, send it to others
                modify_element_in_store(element_id, entry)
                # Start new thread to propagate
                #_begin_propagation(BOARD_MODIFY, element_id, entry)
            # Delete
            else:
                # If deletion was successful, send it to others
                if delete_element_from_store(element_id):
                    # Start new thread to propagate
                    #_begin_propagation(BOARD_DELETE, element_id)
                    pass

        except Exception as e:
            print "Exception occurred at /board/elementid."
            print e
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>')
    def propagation_received(action):
        global entry_sequence

        try:
            entry = request.json

            # Someone has added something to the board
            if action == BOARD_ADD:
                add_new_element_to_store(entry, True)

            elif action == BOARD_DELETE:
                delete_element_from_store(entry, True)

            else:
                modify_element_in_store(entry, request.body.getvalue(), True)

        except Exception as e:
            print "Exception occurred at /propagate."
            print e
            response.status = INTERNAL_SERVER_ERROR


    def begin_propagation(url, payload=None, headers=None):
        """
        Since we use propagate_to_vessels at many places, this method avoid some code duplication because of the thread logic
        :param url: The url to call
        :param payload: What data to send
        :param headers: Extra header information, such as Content-type
        """
        try:
            thread = Thread(target=propagate_to_vessels, args=(url, payload, headers))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print "Exception occurred at /begin_propagation."
            print e

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