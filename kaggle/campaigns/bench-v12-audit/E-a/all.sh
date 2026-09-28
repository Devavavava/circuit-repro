#!/bin/bash
date +%s > /tmp/cr-7cd7ffc3-ab/start.ts
grep -v "^E-a v12-nb-f15-g12 template 0.02 1$" /tmp/cr-7cd7ffc3-ab/jobs.txt | xargs -P 4 -L 1 /tmp/cr-7cd7ffc3-ab/one.sh 2>&1 | grep --line-buffered -v "recursion limit" > /tmp/cr-7cd7ffc3-ab/all.log
date +%s > /tmp/cr-7cd7ffc3-ab/end.ts
