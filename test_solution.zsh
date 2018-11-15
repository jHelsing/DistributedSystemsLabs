#!/bin/zsh

index=1

for ((i = 1; i <= 8; i++)); do
	curl -s -X POST -F 'entry=test.'$index http://10.1.0.$i:80/board > /dev/null
	((index++))
done
