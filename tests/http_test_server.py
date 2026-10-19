"""Loopback fixtures must release request-owned files before temporary-directory cleanup."""
import faulthandler
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer
import sys
import threading
import time


class ThreadingHTTPServer(_ThreadingHTTPServer):
    request_timeout = 15
    close_timeout = 30

    def __init__(self, *args, **kwargs):
        self._request_lock=threading.Lock(); self._requests={}
        super().__init__(*args, **kwargs)

    def get_request(self):
        request, address=super().get_request()
        request.settimeout(self.request_timeout)
        return request, address

    def process_request(self, request, client_address):
        # stdlib ThreadingHTTPServer's daemon handlers are NOT joined by server_close().
        thread=threading.Thread(target=self._handle_request,args=(request,client_address),
                                name=f'http-fixture-{self.server_port}',daemon=True)
        with self._request_lock:
            self._requests[thread]=(request,client_address)
            try:thread.start()
            except BaseException:
                del self._requests[thread]; raise

    def _handle_request(self, request, client_address):
        try:super().process_request_thread(request,client_address)
        finally:
            with self._request_lock:self._requests.pop(threading.current_thread(),None)

    def server_close(self):
        super().server_close()
        deadline=time.monotonic()+self.close_timeout
        with self._request_lock:requests=list(self._requests.items())
        for thread, _ in requests:thread.join(max(0,deadline-time.monotonic()))
        live=[(thread,request,address) for thread,(request,address) in requests if thread.is_alive()]
        if live:
            inventory=[dict(thread=t.name,ident=t.ident,socket=s.fileno(),peer=a) for t,s,a in live]
            print(f'HTTP FIXTURE TEARDOWN TIMEOUT: port={self.server_port} handlers={inventory}',file=sys.stderr,flush=True)
            faulthandler.dump_traceback(file=sys.stderr,all_threads=True)
            raise RuntimeError(f'HTTP fixture {self.server_port} retained {len(live)} handler(s) after {self.close_timeout}s')
