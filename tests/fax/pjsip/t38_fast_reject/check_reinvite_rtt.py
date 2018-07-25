#!/usr/bin/python

import csv
import sys
import re

regex = re.compile("([0-9]{2}):([0-9]{2}):([0-9]{2}):([0-9]{3})([0-9]{3})?")
with open(sys.argv[1]) as csvfile:
    reader = csv.DictReader(csvfile, delimiter=';')
    for row in reader:
        if not row.has_key('ResponseTimereinvite(P)'):
            print "column not found! make sure scenario is correct!\n"
            exit(-1);
        parts = regex.match(row['ResponseTimereinvite(P)'])
        hours = int(parts.group(1))
        minutes = (hours * 60) + int(parts.group(2))
        seconds = (minutes * 60) + int(parts.group(3))
        milliseconds = (seconds * 1000) + int(parts.group(4))
        if (milliseconds > 500):
            print "Slow 488 Rejection detected (" + milliseconds + ")!\n";
            exit(-2)

csvfile.close()
exit(0)