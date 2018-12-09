#!/bin/zsh

targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4)

# Add
index=0
for ip_address in $targets; do
	echo "Current server:" $ip_address
	for i in {0..19}; do
		
		curl -o /dev/null -s -X POST -F 'entry=test.'$index http://$ip_address:80/board

		#if [ $((index%2)) -eq 0 ]; then
		#	modify_entry_status_code=$(curl -o /dev/null -s -w "%{http_code}\n" -X POST -F 'action=0' -F 'entry=modi.'$index http://$ip_address:80/board/$index)
		#	if [ $modify_entry_status_code != "200" ]; then
		#		echo "Could not modify item: "$index
		#	fi
		#if [ $((index%2)) -eq 1 ]; then
		#	delete_entry_status_code=$(curl -o /dev/null -s -w "%{http_code}\n" -X POST -F 'action=1' http://$ip_address:80/board/$index)
		#	if [ $delete_entry_status_code != "200" ]; then
		#		echo "Could not delete item: "$index
		#	fi
		#fi 
		((index++))
	done
done
