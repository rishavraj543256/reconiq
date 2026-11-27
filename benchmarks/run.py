import json
import random
import time
import tracemalloc
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from app.reconciliation import Candidate, ReconciliationEngine, Rule


def benchmark(size: int) -> dict:
    rng = random.Random(42); base = date(2026, 1, 1); left=[]; right=[]
    for i in range(size):
        amount=Decimal(str(rng.randint(100,100000)/100)); ref=f"INV-{i:08d}"; day=base+timedelta(days=i%365)
        left.append(Candidate(f"i{i:08d}",amount,day,ref,"Synthetic Vendor"))
        right.append(Candidate(f"b{i:08d}",amount,day+timedelta(days=i%3),ref,"Synthetic Vendor"))
    tracemalloc.start(); started=time.perf_counter(); matches=ReconciliationEngine().reconcile(left,right,Rule(Decimal("0"),3,90,95)); elapsed=time.perf_counter()-started; _, peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
    correct=sum(1 for x in matches if x.left_id[1:]==x.right_id[1:])
    return {"records_per_side":size,"duration_seconds":round(elapsed,4),"matches":len(matches),"accuracy":round(correct/size,6),"false_matches":len(matches)-correct,"peak_traced_memory_mb":round(peak/1024/1024,2)}


if __name__=="__main__":
    results=[benchmark(n) for n in (1000,10000,100000)]
    Path("benchmark-results.json").write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
