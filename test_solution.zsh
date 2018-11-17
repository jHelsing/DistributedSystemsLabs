#!/bin/zsh

targets=('10.1.0.1' '10.1.0.2' '10.1.0.3' '10.1.0.4' '10.1.0.5' '10.1.0.6' '10.1.0.7' '10.1.0.8')
index=1

for ip_address in $targets; do
	for ((i = 1; i < 4; i++)); do
		curl -s -X POST -F 'entry=test.'$index http://$ip_address:80/board > /dev/null
		((index++))
	done
done
