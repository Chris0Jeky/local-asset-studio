# Inert model-download TLS fixture

This self-signed certificate and public test key are used only by
`test_model_download_transport.py`. The certificate names
`download-fixture.invalid`, and each test creates an isolated trust context for
it. No global trust store is changed. The server exchanges five inert bytes
through a local socket pair; it never resolves or contacts a model provider.

The certificate is valid from 26 October 2026 through 2 October 2126. The key is
deliberately public fixture data and must never be used by an application server.

Generated once with OpenSSL:

```console
openssl req -x509 -newkey rsa:2048 -noenc -sha256 -days 36500 -subj /CN=download-fixture.invalid -addext subjectAltName=DNS:download-fixture.invalid -keyout private-key.pem -out certificate.pem
```
