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

ENTRY_KEY = 'entry'
ACTION_KEY = 'action'
RETRY_KEY = 'retries'
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

    def get_next_index():
        """
        So that I can get the indices
        """
        for i in sorted(board.keys()):
            yield i
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

        # Store the data that we receive for quick access
        received_clock = int(entry_data[CLOCK_KEY])
        received_node_id = int(entry_data[NODE_ID_KEY])

        received_entry = entry_data

        # Define a generator that will help us place the index at the correct position
        generator = get_next_index()

        # This will reflect at which index the new entry should be placed at. If the new item should be placed at the
        # end of the board then this value will remain None
        index = None
        # A help variable that holds an entry
        temp_entry = None

        if is_propagated_call:
            # Loop and look for the correct position
            for i, entry in board.items():
                if received_clock < entry[CLOCK_KEY]:
                    # Save the position where we have added the new item
                    index = i
                    # Store the entry that we are overwriting
                    temp_entry = board[i]
                    # Add the new entry at the current position
                    board[i] = received_entry
                    # Break out of the loop
                    break
                elif received_clock == entry[CLOCK_KEY]:
                    # Favour higher node ids
                    if received_node_id > entry[NODE_ID_KEY]:
                        index = i
                        temp_entry = board[i]
                        board[i] = received_entry
                        # Break out of the loop
                        break

            not_done = True
            # If index is None then we add the item to the back of the board
            if index is not None:
                # Loop unti we have gone through all items in the board
                while not_done:
                    try:
                        # Since we add items to a dictionary we can't just use index+1 to push down every entry 1
                        # position. Consider the following, if we add 3 items to the board and then we delete item 2,
                        # then there will be no board[2] so if we add something at position 1 then the previous entry at
                        # position 1 should now be at position 3 etc.
                        next_index = generator.next()
                        if next_index > index:
                            # Shuffle entries around
                            temp_entry_2 = board[next_index]
                            board[next_index] = temp_entry
                            temp_entry = temp_entry_2
                    # If there are no more keys in the board then we should add the current temp_entry at the bottom of
                    # the board with entry sequence as index
                    except StopIteration:
                        not_done = False
                        board[entry_sequence] = {}
                        board[entry_sequence] = temp_entry
            else:
                # If the item should be placed at the back of the board
                board[entry_sequence] = {}
                board[entry_sequence].update(received_entry)
        else:
            # If the call isn't propagated we just add the item to the board and when a call is propagated we order the
            # messages correctly
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
            entry_info = {
                UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                ENTRY_KEY: received_entry,
                ACTION_KEY: BOARD_MODIFY,
                RETRY_KEY: 1
            }
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
                    if retry:
                        entry_info[RETRY_KEY] = entry_data[RETRY_KEY]+1
                        unhandled_requests.append(entry_info)
                    else:
                        unhandled_requests.append(entry_info)
            else:
                # Board was empty
                if retry:
                    entry_info[RETRY_KEY] = entry_data[RETRY_KEY] + 1
                    unhandled_requests.append(entry_info)
                else:
                    unhandled_requests.append(entry_info)
        else:
            # We deleted an item that was on our own board. We can only call this method locally if that item was on the
            # board at that specific moment. Therefore we don't have to check if the board was empty etc
            for i, entry in board.items():
                if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                    entry[ENTRY_KEY] = received_entry

    def delete_element_from_store(entry_data, is_propagated_call = False, retry=False):
        """
        "Removes" an item from the board
        A limitation with this solution is the following scenario: 2 servers are running (for simplicity) and they have
        2 items on their board each. Now, I send a message to add an item to each board and delete the second entry. On
        server 1 the add message arrives first and it turns out that it should be placed before entry 2 and thus entry 2
        will after the addition of this new item be att position 3, then the delete comes and removes the item at
        position 3. On server 2, the delete message arrives first and deletes the item at index 2, and when the new item
        arrives we add it to position 3. This scenario will cause it to be a difference in the sequence numbers. The
        order will still be the same among messages. However, due to the fact that the sequence number reflects how the
        messages arrived to this board there will sometimes be a small difference due to the fact that we can't look in
        the future and see that we should hold with a certain request. This won't be solved if we look at the recent
        updates to the board either and we can't trust on position in the board at the time of delete either for obvious
        reasons. A way that this can be solved is that when something is added we create a new board and normalize the
        positions but this doesn't preserve the original index at which we added the entry. So, this solution orders
        the messages in the same order across servers but since the different servers get messages in different order,
        therefore the entry sequence number might be different for the same message on another server.
        :param entry_data: information about the entry
        :param is_propagated_call: if this call was sent to us
        :param retry: if we retry to perform this action
        """
        global board, node_id, unhandled_requests, deletes_indicator, recent_deletes

        received_unique_identifier = entry_data[UNIQUE_IDENTIFIER_KEY]

        found_entry_to_delete = False

        if is_propagated_call or retry:
            entry_info = {
                UNIQUE_IDENTIFIER_KEY: received_unique_identifier,
                ACTION_KEY: BOARD_DELETE,
                RETRY_KEY: 1
            }
            # If no messages to add any item to the board then we can't do anything. Add it to the list of unhandled
            # requests
            if len(board) > 0:
                for i, entry in board.items():
                    # Find correct entry
                    if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                        # Delete
                        del board[i]
                        found_entry_to_delete = True
                        break

                if not found_entry_to_delete:
                    # If we didn't find the entry then we add it to unhandled requests.
                    if retry:
                        entry_info[RETRY_KEY] = entry_data[RETRY_KEY]+1
                        unhandled_requests.append(entry_info)
                    else:
                        unhandled_requests.append(entry_info)
            else:
                # Board was empty
                if retry:
                    entry_info[RETRY_KEY] = entry_data[RETRY_KEY] + 1
                    unhandled_requests.append(entry_info)
                else:
                    unhandled_requests.append(entry_info)
        else:
            # We deleted an item that was on our own board. We can only call this method locally if that item was on the
            # board at that specific moment. Therefore we don't have to check if the board was empty etc
            for i, entry in board.items():
                if entry[UNIQUE_IDENTIFIER_KEY] == received_unique_identifier:
                    # Delete
                    del board[i]
                    break

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # should be given to the students?
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload, headers, req='POST'):
        """
        Try to contact another server (vessel) through a POST or GET, once
        :param vessel_ip: target ip
        :param path: target path
        :param payload: data to send
        :param headers: custom headers
        :param req: type of request
        """
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
        """
        Propagate to vessels
        """
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
                # We have tried to modify this message 20 times, this means that the request to add the message to the
                # board hasn't arrived and couldn't arrive. Therefore, remove it
                if unhandled_entry[RETRY_KEY] < 20:
                    modify_element_in_store(unhandled_entry, retry=True)
                # Remove the request
                del unhandled_requests[i]
            elif unhandled_entry[ACTION_KEY] == BOARD_DELETE:
                # We have tried to delete this message 20 times, this means that the request to add the message to the
                # board hasn't arrived and couldn't arrive. Therefore, remove it
                if unhandled_entry[RETRY_KEY] < 20:
                    delete_element_from_store(unhandled_entry, retry=True)
                # Remove the request
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
            # Try to handle requests when a new client requests the main page
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
            # Continuously try to update the board if there are any unhandled requests
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
                NODE_ID_KEY: node_id    # If two clock values are the same we use node_id to determine the placement
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