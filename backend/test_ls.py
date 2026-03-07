import os
import json
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

client = Client()
trace_id = "80827971-65ae-42b8-8f19-e19c6c845ebb" # From the output above

runs = list(client.list_runs(trace_id=trace_id))

runs_by_id = {str(r.id): r for r in runs}

def get_lineage(run_id):
    lineage = []
    curr = run_id
    while curr:
        r = runs_by_id.get(str(curr))
        if not r: break
        lineage.append(r.name)
        curr = r.parent_run_id
    return lineage

for r in runs:
    if r.run_type == "llm":
        print(f"LLM RUN: {r.name} id={r.id}")
        lineage = get_lineage(r.id)
        # remove the root
        print(f"  Lineage: {' -> '.join(lineage[::-1])}")
