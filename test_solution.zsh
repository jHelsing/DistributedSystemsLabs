#!/bin/zsh

targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4 10.1.0.5 10.1.0.6 10.1.0.7 10.1.0.8)

# Add
index=1
for ip_address in $targets; do
	for i in {1..3}; do
		curl -s -X POST -F 'entry=test.'$index http://$ip_address:80/board > /dev/null
		((index++))
	done
done

index=1
for ip_address in $targets; do
	for i in {1..3}; do
		if [ $((index%2)) -eq 0 ]; then
			# Modify
			curl -s -X POST -F 'action=0' -F 'entry=modi.'$index http://$ip_address:80/board/$index > /dev/null
		else
			# Delete
			curl -s -X POST -F 'action=1' http://$ip_address:80/board/$index > /dev/null
		fi
		((index++))
	done
done
