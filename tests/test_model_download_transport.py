"""No provider traffic: fake TCP peers, real urllib, and an inert local TLS exchange."""
from contextlib import contextmanager
import http.client
import io
from pathlib import Path
import socket
import ssl
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import ProxyHandler,Request

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
import download_contracts as contracts


def public_resolver(host,port,**kwargs):return [(2,1,6,'',('93.184.216.34',port))]


class ResponseBytes(io.BytesIO):
    def __init__(self,body,events,name):super().__init__(body);self.events=events;self.name=name
    def close(self):
        if not self.closed:self.events.append(('response-close',self.name))
        super().close()


class InertSocket:
    def __init__(self,address,events,name='model',responses=None):
        self.address=address;self.events=events;self.name=name;self.closed=False;self.sent=[]
        self.responses=list(responses or [b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n'])
    def setsockopt(self,*args):pass
    def getpeername(self):self.events.append(('peer',self.name));return self.address,443
    def sendall(self,data):self.sent.append(data);self.events.append(('send',self.name))
    def makefile(self,mode):return ResponseBytes(self.responses.pop(0),self.events,self.name)
    def close(self):self.closed=True


@contextmanager
def inert_transport(sockets,proxies=None,tls_error=None):
    """Replace only dialing and TLS I/O; urllib's connect, tunnel and redirect paths stay real."""
    pending=iter(sockets);context=ssl.create_default_context()
    def dial(address,timeout,source_address):
        sock=next(pending);sock.events.append(('dial',sock.name,address));return sock
    def wrap(sock,server_hostname):
        sock.events.append(('tls',sock.name,server_hostname,context.check_hostname,context.verify_mode))
        if tls_error is not None:raise tls_error
        return sock
    with patch('urllib.request.getproxies',return_value=proxies or {}),patch('urllib.request.proxy_bypass',return_value=False),\
            patch.object(socket,'create_connection',side_effect=dial),\
            patch.object(ssl,'_create_default_https_context',return_value=context),\
            patch.object(context,'wrap_socket',side_effect=wrap):yield


class PeerAddressTests(unittest.TestCase):
    def test_rebound_private_peer_is_closed_before_tls_or_get(self):
        for address in ('10.0.0.5','127.0.0.1','169.254.169.254','::1','224.0.0.1'):
            with self.subTest(address=address):
                events=[];sock=InertSocket(address,events)
                with inert_transport([sock]),self.assertRaises(ValueError):
                    contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver)
                self.assertFalse(any(event[0]=='tls' for event in events),events)
                self.assertEqual(sock.sent,[]);self.assertTrue(sock.closed)

    def test_public_direct_peer_is_checked_then_uses_verified_tls_and_origin_sni(self):
        events=[];sock=InertSocket('93.184.216.34',events)
        with inert_transport([sock]):
            with contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver) as response:
                self.assertEqual(response.read(),b'')
        self.assertEqual([event[0] for event in events[:4]],['dial','peer','tls','send'])
        self.assertIn(('tls','model','huggingface.co',True,ssl.CERT_REQUIRED),events)
        self.assertTrue(sock.sent[0].startswith(b'GET /model HTTP/1.1\r\n'))

    def test_configured_private_proxy_tunnels_then_uses_origin_sni_and_verified_tls(self):
        events=[];sock=InertSocket('127.0.0.1',events,responses=[
            b'HTTP/1.1 200 Connection established\r\n\r\n',
            b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n'])
        with inert_transport([sock],proxies={'https':'http://operator-proxy.invalid:3128'}):
            contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver).close()
        self.assertEqual(events[0],('dial','model',('operator-proxy.invalid',3128)))
        self.assertTrue(sock.sent[0].startswith(b'CONNECT huggingface.co:443 HTTP/1.1\r\n'))
        self.assertTrue(sock.sent[1].startswith(b'GET /model HTTP/1.1\r\n'))
        self.assertFalse(any(event[0]=='peer' for event in events))
        self.assertIn(('tls','model','huggingface.co',True,ssl.CERT_REQUIRED),events)

    def test_tls_certificate_failure_closes_transport_without_get(self):
        events=[];sock=InertSocket('93.184.216.34',events)
        failure=ssl.SSLCertVerificationError('untrusted certificate')
        with inert_transport([sock],tls_error=failure),self.assertRaises(URLError) as caught:
            contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver)
        self.assertIs(caught.exception.reason,failure);self.assertTrue(sock.closed);self.assertEqual(sock.sent,[])

    def test_non_transport_handler_does_not_remove_peer_validation(self):
        events=[];sock=InertSocket('127.0.0.1',events)
        with inert_transport([sock]),self.assertRaises(ValueError):
            contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver,
                                    transport_handlers=(ProxyHandler({}),))
        self.assertFalse(any(event[0]=='tls' for event in events),events)
        self.assertEqual(sock.sent,[]);self.assertTrue(sock.closed)

    def test_redirect_response_is_closed_before_next_hop_connect_failure(self):
        # Characterize the real urllib boundary: http_error_302 drains/closes before parent.open.
        events=[];first=InertSocket('93.184.216.34',events,'first',[
            b'HTTP/1.1 302 Found\r\nLocation: https://cdn-lfs-us-1.hf.co/model\r\nContent-Length: 6\r\n\r\nignore'])
        second=InertSocket('127.0.0.1',events,'second')
        with inert_transport([first,second]),self.assertRaises(ValueError):
            contracts.open_download(Request('https://huggingface.co/model'),resolver=public_resolver)
        self.assertLess(events.index(('response-close','first')),
                        events.index(('dial','second',('cdn-lfs-us-1.hf.co',443))))
        self.assertEqual(second.sent,[]);self.assertTrue(first.closed);self.assertTrue(second.closed)


class PublicFixtureSocket(socket.socket):
    """The socketpair stays local; only its reported address models a provider peer."""
    def getpeername(self):return '93.184.216.34',443
    def setsockopt(self,level,option,value):
        # Unix socketpairs have no Nagle algorithm; Windows socketpairs use TCP.
        if self.family==getattr(socket,'AF_UNIX',None) and (level,option)==(socket.IPPROTO_TCP,socket.TCP_NODELAY):return
        return super().setsockopt(level,option,value)


class RealTLSContextTests(unittest.TestCase):
    def exchange(self,hostname='download-fixture.invalid',proxy=False):
        fixture=Path(__file__).parent/'fixtures/model-download-tls'
        server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(fixture/'certificate.pem',fixture/'private-key.pem')
        client_context=ssl.create_default_context(cafile=str(fixture/'certificate.pem'))
        observed={'sni':[],'requests':[],'connect':b'','errors':[]}
        server_context.set_servername_callback(lambda sock,name,context:observed['sni'].append(name))
        client,server=socket.socketpair();client=PublicFixtureSocket(fileno=client.detach())
        client.settimeout(3);server.settimeout(3)
        def serve():
            try:
                if proxy:
                    while not observed['connect'].endswith(b'\r\n\r\n'):
                        data=server.recv(4096)
                        if not data:raise OSError('Proxy fixture disconnected')
                        observed['connect']+=data
                    server.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
                with server_context.wrap_socket(server,server_side=True) as secured:
                    observed['requests'].append(secured.recv(4096))
                    secured.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\ninert')
            except (OSError,ssl.SSLError) as exc:observed['errors'].append(exc)
            finally:server.close()
        worker=threading.Thread(target=serve,daemon=True);worker.start()
        connection=contracts._PeerCheckedHTTPSConnection('operator-proxy.invalid' if proxy else hostname,
                                                        timeout=3,context=client_context)
        connection._create_connection=lambda *args:client
        if proxy:connection.set_tunnel(hostname,443)
        try:
            connection.request('GET','/fixture')
            with connection.getresponse() as response:observed['body']=response.read()
        except (OSError,ssl.SSLError) as exc:observed['failure']=exc
        finally:connection.close();client.close();worker.join(timeout=4)
        self.assertFalse(worker.is_alive(),'TLS fixture did not stop')
        return observed

    def test_real_tls_authenticates_the_origin_directly_and_through_a_proxy(self):
        for proxy in (False,True):
            with self.subTest(proxy=proxy):
                observed=self.exchange(proxy=proxy)
                self.assertNotIn('failure',observed);self.assertEqual(observed['errors'],[])
                self.assertEqual(observed['body'],b'inert');self.assertEqual(observed['sni'],['download-fixture.invalid'])
                self.assertTrue(observed['requests'][0].startswith(b'GET /fixture HTTP/1.1\r\n'))
                if proxy:self.assertTrue(observed['connect'].startswith(b'CONNECT download-fixture.invalid:443 HTTP/1.1\r\n'))

    def test_real_tls_rejects_hostname_mismatch_before_get(self):
        for proxy in (False,True):
            with self.subTest(proxy=proxy):
                observed=self.exchange(hostname='different-host.invalid',proxy=proxy)
                self.assertIsInstance(observed.get('failure'),ssl.SSLCertVerificationError)
                self.assertEqual(observed['requests'],[])


if __name__=='__main__':unittest.main()
