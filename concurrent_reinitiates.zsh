

curl -s -X POST -F 'entry=test.2' http://10.1.0.5:80/board > /dev/null
curl -s -X POST -F 'entry=test.1' http://10.1.0.3:80/board > /dev/null
curl -s -X POST -F 'entry=test.2' http://10.1.0.4:80/board > /dev/null
curl -s -X POST -F 'entry=test.1' http://10.1.0.2:80/board > /dev/null
curl -s -X POST -F 'entry=test.2' http://10.1.0.6:80/board > /dev/null
curl -s -X POST -F 'entry=test.1' http://10.1.0.7:80/board > /dev/null
curl -s -X POST -F 'entry=test.1' http://10.1.0.1:80/board > /dev/null
curl -s -X POST -F 'entry=test.2' http://10.1.0.8:80/board > /dev/null