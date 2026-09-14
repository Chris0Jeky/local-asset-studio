"""Regression contract for the class-level AV client HTTP fixture."""
import unittest

import test_av_client as av_client


class ClientFixtureLifetimeTests(unittest.TestCase):
    def test_teardown_closes_listener_and_stops_serving_thread(self):
        av_client.ClientTests.setUpClass()
        server = av_client.ClientTests.server
        thread = av_client.ClientTests.thread
        self.assertGreaterEqual(server.fileno(), 0)

        closed = False
        stopped = False
        try:
            av_client.ClientTests.tearDownClass()
            closed = server.fileno() == -1
            stopped = not thread.is_alive()
        finally:
            # Keep a failing regression assertion from leaking its own listener.
            if thread.is_alive():
                server.shutdown()
                thread.join(timeout=5)
            if server.fileno() != -1:
                server.server_close()

        self.assertTrue(closed, "tearDownClass must close the listening socket")
        self.assertTrue(stopped, "tearDownClass must stop the serving thread")


if __name__ == "__main__":
    unittest.main()
