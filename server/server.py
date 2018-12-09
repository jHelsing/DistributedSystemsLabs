# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 3
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: Anton Solback
# ------------------------------------------------------------------------------------------------------
import time
from itertools import tee
import argparse
import traceback
import operator
from datetime import datetime
from threading import Thread

from bottle import Bottle, run, request, template, response
import requests

BOARD_ADD = 'add'
BOARD_DELETE = 'delete'
BOARD_MODIFY = 'modify'

ENTRY_ACTIVE = 'active'
ENTRY_DELETED = 'deleted'

ENTRY_KEY = 'entry'
ACTION_KEY = 'action'
STATUS_KEY = 'status'
ID_KEY = 'id'
NODE_ID_KEY = 'node_id'
CLOCK_KEY = 'logical_clock'
UNIQUE_IDENTIFIER_KEY = 'unique_identifier'

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

JSON_DATA_HEADER = {'content-type':'application/json'}

OK = 200
BAD_REQUEST = 400
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
            unique_identifier: hash(timestamp + entry)
        }
    }
    """
    board = {}

    clock = 0

    # Initialize an array with 30 entries, doesn't matter what the values are
    recent_deletes = [str(i) for i in range(0,30)]
    deletes_indicator = 0

    unhandled_requests = []

    # Each entry gets a sequence number
    entry_sequence = 0

    # ------------------------------------------------------------------------------------------------------
    # HELPER FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
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
        except Exception:
            print "Exception occurred at /begin_propagation."
            traceback.print_exc()
    # ------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # Should nopt be given to the student
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_data, is_propagated_call=False):
        """
        Adds new element to the board
        :param entry_data: info about the new entry
        :param is_propagated_call: if this action was sent from another server
        """
        global board, entry_sequence, remote_updates, local_updates
        received_clock = int(entry_data[CLOCK_KEY])
        received_node_id = int(entry_data[NODE_ID_KEY])

        found_correct_placement = False

        received_entry = entry_data
        received_entry[STATUS_KEY] = ENTRY_ACTIVE

        if is_propagated_call:
            # Create new board
            new_board = {}

            # Find position where we want to add entry
            for i, entry in board.items():

                # If we want to add an item in between an entry then we need to push back the remaining items in the
                # board. In a real-worl scenario you would obviously use a database instead
                if found_correct_placement:
                    new_board[i+1] = {}
                    new_board[i+1].update(entry)
                    # We just need to push back the remaining items
                    continue

                # Create new entry at position i
                new_board[i] = {}

                if entry[CLOCK_KEY] < received_clock:
                    # If the current cloch has a smaller value than the one received we just add the current item to
                    # the same place that it previously had
                    new_board[i].update(entry)
                elif received_clock < entry[CLOCK_KEY]:
                    # Push back the entry at the current index by one and insert the received entry at the current index
                    new_board[i].update(received_entry)

                    new_board[i+1] = {}
                    new_board[i+1].update(entry)

                    # Indicate that we have inserted the new item
                    found_correct_placement = True
                else:
                    # If the current entry's clock is equal to the one received. In this case we need to look at node id
                    # to determine the correct placement. We favour higher ID's
                    if entry[NODE_ID_KEY] > received_node_id:
                        new_board[i].update(entry)
                        new_board[i+1] = {}
                        new_board[i+1].update(received_entry)
                    else:
                        new_board[i].update(received_entry)

                        new_board[i+1] = {}
                        new_board[i+1].update(entry)

                    # We have found the correct placement. Now we need to push back all resuming entries one step
                    found_correct_placement = True

            # See if we found the correct placement
            if found_correct_placement is False:
                # If this is false then we should add the item to the end of the board. Therefore, we can use the
                # the entry_sequence or placement
                new_board[entry_sequence] = {}
                new_board[entry_sequence].update(received_entry)

            # Set the previous board to the new one
            board = new_board
        else:
            # When we add to our own board we just add it to the current value of the the entry_sequence counter.
            # We don't need to check order since that will be done when a call is propagated to us
            board[entry_sequence] = {}
            board[entry_sequence].update(received_entry)

        # Always increment to keep up to date
        entry_sequence += 1

    def modify_element_in_store(entry_data, is_propagated_call = False, retry=False):
        """
        Modifies an item on the board by changing that entries status to be deleted
        :param entry_data: information about the entry
        :param is_propagated_call: if this call was sent to us
        :param retry: if we retry to perform this action
        """
        global board, node_id, remote_updates, local_updates, unhandled_requests

        # Identifier of the entry that we want to modify
        received_unique_identifier = entry_data[UNIQUE_IDENTIFIER_KEY]
        # The new entry
        received_entry = entry_data[ENTRY_KEY]

        found_entry_to_modify = False

        if is_propagated_call or retry:
            # If no messages to add any item to the board then we can't do anything. Add it to the list of unhandled
            # requests
            if len(board) > 0:
                for i, entry in board.items():
                    # Find correct entry
                    if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                        # Modify entry
                        entry[ENTRY_KEY] = received_entry
                        found_entry_to_modify = True

                if not found_entry_to_modify:
                    # If we didn't find the entry then we add it to unhandled requests.
                    unhandled_requests.append({
                        ENTRY_KEY: received_entry,
                        UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                        ACTION_KEY: BOARD_MODIFY
                    })
            else:
                # Board was empty
                unhandled_requests.append({
                    ENTRY_KEY: received_entry,
                    UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                    ACTION_KEY: BOARD_MODIFY
                })
        else:
            # We deleted an item that was on our own board. We can only call this method locally if that item was on the
            # board at that specific moment. Therefore we don't have to check if the board was empty etc
            for i, entry in board.items():
                if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                    entry[ENTRY_KEY] = received_entry

    def delete_element_from_store(entry_data, is_propagated_call = False, retry=False):
        """
        "Removes" an item from the board by changing that entries status to be deleted
        :param entry_data: information about the entry
        :param is_propagated_call: if this call was sent to us
        :param retry: if we retry to perform this action
        """
        global board, node_id, unhandled_requests, deletes_indicator, recent_deletes

        received_unique_identifier = entry_data[UNIQUE_IDENTIFIER_KEY]

        found_entry_to_delete = False

        if is_propagated_call or retry:
            # If no messages to add any item to the board then we can't do anything. Add it to the list of unhandled
            # requests
            if len(board) > 0:
                for i, entry in board.items():
                    # Find correct entry
                    if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                        # Change its status
                        entry[STATUS_KEY] = ENTRY_DELETED
                        found_entry_to_delete = True

                if not found_entry_to_delete:
                    # If we didn't find the entry then we add it to unhandled requests.
                    unhandled_requests.append({
                        UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                        ACTION_KEY: BOARD_DELETE
                    })
            else:
                # Board was empty
                unhandled_requests.append({
                    UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                    ACTION_KEY: BOARD_DELETE
                })
        else:
            # We deleted an item that was on our own board. We can only call this method locally if that item was on the
            # board at that specific moment. Therefore we don't have to check if the board was empty etc
            for i, entry in board.items():
                if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                    entry[STATUS_KEY] = ENTRY_DELETED

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # should be given to the students?
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload, headers, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                # If we want to send json data, use the json parameter in post
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
        except Exception:
            print "Exception occurred at contact vessels"
            traceback.print_exc()

        return success

    def propagate_to_vessels(path, payload=None, headers=None, req='POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if vessel_id != node_id:  # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, headers, req=req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    def handle_unhandled_requests():
        """
        Try to modify/delete an entry that we have had the request to do but was unable at the time
        """
        global unhandled_requests, board

        # Go through each unhandled entry and try to delete/modify
        for i, unhandled_entry in enumerate(unhandled_requests):
            if unhandled_entry[ACTION_KEY] == BOARD_MODIFY:
                modify_element_in_store(unhandled_entry, retry=True)
                del unhandled_requests[i]
            if unhandled_entry[ACTION_KEY] == BOARD_DELETE:
                delete_element_from_store(unhandled_entry, retry=True)
                del unhandled_requests[i]


    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id, remote_updates
        try:
            handle_unhandled_requests()

            # Sort dictionary on the entry_number in the dictionary
            return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)), members_name_string='Anton Solback')
        except Exception:
            print "Exception occurred at /."
            traceback.print_exc()

    @app.get('/board')
    def get_board():
        global board, node_id, remote_updates
        try:
            # If there were any deletes/modifies that we couln't handle at the time, see if we can process them now
            handle_unhandled_requests()

            # Sort dictionary on the entry_number in the dictionary
            return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.items(), key=operator.itemgetter(0)))
        except Exception:
            print "Exception occurred at /board (get)."
            traceback.print_exc()
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        """
        Adds a new element to the board
        """
        global board, node_id, entry_sequence, clock
        try:
            # Get the text
            print datetime.now()
            entry = request.forms.get('entry')

            # Increase the clock
            clock += 1

            # The required data
            entry_data = {
                CLOCK_KEY: clock,
                ENTRY_KEY: entry,
                # Create a unique identifier instead, this makes it much simpler when looking for the correct item
                # Optimally this should be hashed as well, but we are satisfied with this at the moment
                UNIQUE_IDENTIFIER_KEY: str(clock)+entry+str(node_id)+datetime.now().strftime(TIMESTAMP_FORMAT),
                NODE_ID_KEY: node_id # If two clock values are the same we use node_id to determine the placement
            }

            # Add the element, we don't catch exception in add_new_element_to_store so if the add wasn't successful,
            # we return a INTERNAL_SERVER_ERROR
            add_new_element_to_store(entry_data)
            # Propagate
            begin_propagation("/propagate/{}".format(BOARD_ADD), entry_data, JSON_DATA_HEADER)

        except Exception:
            print "Exception occurred at /board (post)."
            traceback.print_exc()
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):
        """
        Receives an request to either modify or delete an item
        """
        global clock
        try:
            action_to_perform = request.forms.get('action')
            entry = request.forms.get("entry")
            # Increase clock value
            clock += 1

            # We can only modify items that are currently in the bord. This also prevents from users typing
            # IP/board/10000000 etc in the hopes to try and break the server
            if board.get(element_id) is not None:
                # Modify
                if action_to_perform == "0":
                    # Required data to send to other servers
                    entry_data = {
                        UNIQUE_IDENTIFIER_KEY: board[element_id][UNIQUE_IDENTIFIER_KEY],
                        ENTRY_KEY: entry,
                        CLOCK_KEY: clock
                    }
                    # I don't capture exceptions in modify_element_in_store so if there is an exception we return an
                    # INTERNAL_SERVER_ERROR
                    modify_element_in_store(entry_data)
                    # Start new thread to propagate
                    begin_propagation("/propagate/{}".format(BOARD_MODIFY), entry_data, JSON_DATA_HEADER)
                # Delete
                elif action_to_perform == "1":
                    entry_data = {
                        UNIQUE_IDENTIFIER_KEY: board[element_id][UNIQUE_IDENTIFIER_KEY],
                        CLOCK_KEY: clock
                    }
                    # I don't capture exceptions in delete_element_in_store so if there is an exception we return an
                    # INTERNAL_SERVER_ERROR
                    delete_element_from_store(entry_data)
                    # Start new thread to propagate
                    begin_propagation("/propagate/{}".format(BOARD_DELETE), entry_data, JSON_DATA_HEADER)
            else:
                # If the user requested to change an id that isn't in the board then return BAD_REQUEST
                response.status = BAD_REQUEST

        except Exception:
            print "Exception occurred at client_action_received"
            traceback.print_exc()
            response.status = INTERNAL_SERVER_ERROR

    @app.post('/propagate/<action>')
    def propagation_received(action):
        """
        A server receives a propagation. Determine the specific action
        """
        global entry_sequence, clock

        try:
            print datetime.now()
            entry = request.json

            # Update the clock value
            clock = max(int(entry[CLOCK_KEY]), clock)+1

            # Someone has added something to the board
            if action == BOARD_ADD:
                add_new_element_to_store(entry, True)

            # Delete
            elif action == BOARD_DELETE:
                delete_element_from_store(entry, True)

            # Modify
            elif action == BOARD_MODIFY:
                modify_element_in_store(entry, True)

        except Exception:
            print "Exception occurred at /propagate."
            traceback.print_exc()
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
            vessel_list[i] = '10.1.0.{}'.format(str(i))

        try:
            run(app, host=vessel_list[node_id], port=port)
        except Exception:
            traceback.print_exc()
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)