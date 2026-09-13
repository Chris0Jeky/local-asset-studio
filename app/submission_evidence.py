"""Classify retained submission evidence, never a queue label alone.

Every Studio POST is preceded by a durable pending_submission marker. Missing or
malformed receipt collections cannot prove a request was never sent. These
predicates do not observe or cancel the remote queue and never grant retries.
"""
from __future__ import annotations


def never_submitted(job):
    return (isinstance(job, dict)
            and job.get('status') in ('queued', 'waiting', 'not_submitted', 'uncertain')
            and 'pending_submission' not in job
            and 'abandonment' not in job
            and not job.get('tracking_disposition')
            and all(type(job.get(key)) is list and not job[key]
                    for key in ('prompt_ids', 'submissions', 'outputs')))


def abandonable(job):
    # Known prompts keep the existing, reversible Stop tracking / Resume path.
    # An active worker must first stop or be recovered after restart.
    return (isinstance(job, dict) and job.get('status') in ('not_submitted', 'uncertain')
            and type(job.get('prompt_ids')) is list and not job['prompt_ids']
            and type(job.get('submissions')) is list and not job['submissions']
            and type(job.get('outputs')) is list and not job['outputs']
            and not job.get('tracking_disposition') and 'abandonment' not in job)


def terminal_failure(job):
    """A negative known-prompt result, never an unresolved mixed batch tail."""
    if not isinstance(job,dict) or job.get('status') not in ('failed','partial') or 'pending_submission' in job:return False
    ids=job.get('prompt_ids');receipts=job.get('submissions')
    if not isinstance(ids,list) or not ids or not all(isinstance(i,str) and i.strip() for i in ids):return False
    if len(set(ids))!=len(ids) or not isinstance(receipts,list) or len(receipts)!=len(ids):return False
    if not all(isinstance(s,dict) and s.get('prompt_id')==i and s.get('status') in ('completed','failed') for i,s in zip(ids,receipts)):return False
    if job['status']=='failed':return any(s['status']=='failed' for s in receipts)
    return (type(job.get('batch_count')) is int and len(receipts)<job['batch_count']
            and all(s['status']=='completed' for s in receipts))
