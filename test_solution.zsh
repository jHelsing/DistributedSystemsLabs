#!/bin/zsh

targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4 10.1.0.5 10.1.0.6 10.1.0.7 10.1.0.8)
#targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4)

index=0
for ip_address in $targets; do
	echo "Current server:" $ip_address
	for i in {0..2}; do
		curl -o /dev/null -s -X POST -F 'entry=test.'$index http://$ip_address:80/board
		((index++))
	done
done
	
# Delete/Modify
index=0
for ip_address in $targets; do
	echo "Current server:" $ip_address
	for i in {0..2}; do
		if [ $((index%2)) -eq 0 ]; then
			curl -o /dev/null -s -X POST -F 'action=0' -F 'entry=modi.'$index http://$ip_address:80/board/$index
			#curl -o /dev/null -s -X POST -F 'action=1' http://$ip_address:80/board/$index
		fi
		((index++))
	done
done
