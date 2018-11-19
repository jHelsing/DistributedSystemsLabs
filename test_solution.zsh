#!/bin/zsh

index=1

for i in {1..8}; do
	curl -s -X POST -F 'entry=test.'$index http://10.1.0.$i:80/board > /dev/null
	((index++))
done
