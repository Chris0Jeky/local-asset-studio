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
