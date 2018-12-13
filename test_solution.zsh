#!/bin/zsh

targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4 10.1.0.5 10.1.0.6 10.1.0.7 10.1.0.8)

index=0
for i in {0..3}; do
	for ip_address in $targets; do		
		echo "Current server:" $ip_address
		curl -o /dev/null -s -X POST -F 'entry=test.'$index http://$ip_address:80/board
		if [ $index -gt 4 ]; then
			#status_code=$(curl -o /dev/null -s -w "\n%{http_code}" -X POST -F 'action=0' -F 'entry=modi.'$((index-4)) http://$ip_address:80/board/$((index-4)))
			status_code=$(curl -o /dev/null -s -w "\n%{http_code}" -X POST -F 'action=1' http://$ip_address:80/board/$((index-4)))
			if [ $status_code = "400" ]; then
				echo "Couldn't perform action on message"
			fi
		fi
		((index++))
	done
done








































if [ 1 -eq 0 ]; then

	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi1' http://10.1.0.1:80/board/0
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi2' http://10.1.0.2:80/board/0
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi3' http://10.1.0.3:80/board/0
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi4' http://10.1.0.4:80/board/0

	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi1' http://10.1.0.1:80/board/1
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi2' http://10.1.0.4:80/board/1
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi3' http://10.1.0.3:80/board/1
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi4' http://10.1.0.2:80/board/1

	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi1' http://10.1.0.1:80/board/2
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi2' http://10.1.0.3:80/board/2
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi3' http://10.1.0.4:80/board/2
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi4' http://10.1.0.2:80/board/2

	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi1' http://10.1.0.4:80/board/3
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi2' http://10.1.0.2:80/board/3
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi3' http://10.1.0.3:80/board/3
	curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi4' http://10.1.0.1:80/board/3

	# Delete/Modify
	index=0
	for i in {0..2}; do
		#echo "Current server:" $ip_address
		for ip_address in $targets; do
			if [ $((index%2)) -eq 0 ]; then
				#curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi.'$index http://$ip_address:80/board/$index
				#curl -o /dev/null -s -X POST -F 'action=1' http://$ip_address:80/board/$index
			fi
			((index++))
		done
	done
fi
