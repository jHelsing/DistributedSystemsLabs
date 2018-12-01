#!/bin/zsh

processes=$(pidof xterm)

for pid in ${(ps: :)processes}; do
	sudo kill $pid
done

sudo python lab1.py