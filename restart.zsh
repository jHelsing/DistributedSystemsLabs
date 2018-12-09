#!/bin/zsh

processes=$(pidof xterm)

for pid in ${(ps: :)processes}; do
	sudo kill $pid
done

if [ -n "$1" ]; then
	if [ "$1" -gt 0 ] && [ "$1" -lt 9 ]; then
		sudo python lab1.py --servers $1
	else 
		sudo python lab1.py --servers 8
	fi
else
	sudo python lab1.py --servers 8
fi
