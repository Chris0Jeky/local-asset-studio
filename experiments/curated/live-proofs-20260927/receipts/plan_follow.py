# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
PID = 'cd3c581291914ccf806483ee38763656'; OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
rec = json.load(open(OUT + 'plan-live.json')); t0 = rec['t_start']; peak = 0
while True:
    code, p = drive.studio('/api/production/' + PID)
    st = p.get('state', {}) if isinstance(p, dict) else {}
    jobs = [j for j in drive.studio('/api/jobs')[1] if j.get('project_id') == PID]
    peak = max(peak, drive.commit()['pct'])
    if st.get('status') not in ('queued', 'running', 'observing', 'planned', 'in_progress') and jobs and all(j['status'] not in drive.ACTIVE for j in jobs): break
    time.sleep(10)
done = time.time()
rec['follow'] = {'project': p, 'finished_seen_at': done, 'wall_from_start_s': round(done - t0, 1), 'commit_peak_pct_sampled_10s': peak,
                 'jobs': [{k: j.get(k) for k in ('id', 'preset_id', 'status', 'message', 'prompt_ids', 'batch_count', 'elapsed_seconds', 'created_at', 'started_at', 'finished_at', 'controls', 'outputs')} for j in jobs],
                 'log_after': drive.log_counts(), 'queue_after': drive.queue()}
json.dump(rec, open(OUT + 'plan-live.json', 'w'), indent=1)
print('state', st.get('status'), st.get('message')); print('wall', rec['follow']['wall_from_start_s'], 'estimate', (p.get('combine') or {}).get('estimate'))
for j in rec['follow']['jobs']: print(j['id'][:8], j['preset_id'], j['status'], j['prompt_ids'], round(j['elapsed_seconds'] or 0, 1), (j['controls'] or {}).get('seed'))
print('log', rec['log_before'], rec['follow']['log_after'], rec['follow']['queue_after'], 'peak', peak)
