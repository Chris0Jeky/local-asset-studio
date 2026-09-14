"""CLI projections of shared authoring commands; request keys are explicit."""
from pathlib import Path
from .file_input import read_document
from .sdk import WorkflowClient


def add_parser(sub):
    parent = sub.add_parser('documents', help='Shared workflow documents, revisions and commands')
    commands = parent.add_subparsers(dest='document_command', required=True)
    for name in ('list', 'get', 'create', 'apply', 'preview', 'history', 'restore', 'fork'):
        p = commands.add_parser(name)
        p.add_argument('--out', type=Path)
        if name not in ('list', 'create'): p.add_argument('document_id')
        if name in ('create', 'apply', 'restore', 'fork'): p.add_argument('--request-id', required=True)
        if name == 'create': p.add_argument('--document', required=True, type=Path)
        if name in ('apply', 'preview'):
            p.add_argument('--commands', required=True, type=Path)
        if name in ('apply', 'preview', 'restore'): p.add_argument('--expected-revision', required=True, type=int)
        if name in ('get', 'restore', 'fork'): p.add_argument('--revision', required=name != 'get', type=int)
        if name == 'fork': p.add_argument('--name', required=True)


def execute(args):
    client = WorkflowClient(args.url, args.http_timeout)
    command = args.document_command
    if command == 'list': return client.documents()
    if command == 'get': return client.get_document(args.document_id, args.revision)
    if command == 'history': return client.history(args.document_id)
    if command == 'create':
        return client.create_document(read_document(args.document), request_id=args.request_id)
    if command in ('apply', 'preview'):
        kwargs = {'expected_revision': args.expected_revision}
        if command == 'apply': kwargs['request_id'] = args.request_id
        return getattr(client, command)(args.document_id, read_document(args.commands), **kwargs)
    if command == 'restore':
        return client.restore(args.document_id, args.revision, expected_revision=args.expected_revision, request_id=args.request_id)
    if command == 'fork':
        return client.fork(args.document_id, args.revision, args.name, request_id=args.request_id)
    raise ValueError('Unknown document command')
