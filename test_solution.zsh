#!/bin/zsh

targets=(10.1.0.1 10.1.0.2 10.1.0.3 10.1.0.4 10.1.0.5 10.1.0.6 10.1.0.7 10.1.0.8)

# Add
index=0
for ip_address in $targets; do
	for i in {0..1}; do
		curl -s -X POST -F 'entry=test.'$index http://$ip_address:80/board > /dev/null
		((index++))
	done
done
