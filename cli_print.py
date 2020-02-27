import json
import sys

log = json.loads(sys.stdin.read())

for test in log["tests"]:
    print(test["title"])
    for i, run in enumerate(test["runs"], start=1):
        print()
        print("---- run {} ----".format(i))
        for output in run["output"]:
            print(output["msg"])