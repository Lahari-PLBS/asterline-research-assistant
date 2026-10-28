# compare.py - shows two evaluation runs side by side:  python compare.py before after
import json
import sys

first = json.load(open('eval_results/' + sys.argv[1] + '.json'))['summary']
second = json.load(open('eval_results/' + sys.argv[2] + '.json'))['summary']
for key in first:
    print(key.ljust(22), str(first[key]).rjust(5), '->', str(second.get(key)).rjust(5))