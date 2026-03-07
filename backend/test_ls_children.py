import os
import json
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()
client = Client()
trace_id = "80827971-65ae-42b8-8f19-e19c6c845ebb"

runs = list(client.list_runs(trace_id=trace_id))
root_id = str([r for r in runs if not r.parent_run_id][0].id)
print("ROOT:", root_id)

children = [r for r in runs if str(r.parent_run_id) == root_id]
print("CHILDREN OF ROOT:")
for c in children:
    print(f"  {c.name} id={c.id}")
