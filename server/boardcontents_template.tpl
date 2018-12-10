<!-- this place will show the actual contents of the blackboard. 
It will be reloaded automatically from the server -->
<div id="boardcontents_placeholder">
	<!-- The title comes here -->
	<div id="boardtitle_placeholder" class="boardtitle">{{board_title}}</div>
    <input type="text" name="id" value="ID" readonly>
    <input type="text" name="entry" value="Entry" size="70%%" readonly>
    % for i in range(0, len(board_dict)):
        <form class="entryform" target="noreload-form-target" method="post" action="/board/{{board_dict[i][0]}}">
            <input type="text" name="id" value="{{board_dict[i][0]}}" readonly disabled> <!-- disabled field won’t be sent -->
            <input type="text" name="entry" value="{{board_dict[i][1]["entry"]}}" size="70%%">
            <button type="submit" name="action" value="0">Modify</button>
            <button type="submit" name="action" value="1">X</button>
        </form>
    %end
</div>
