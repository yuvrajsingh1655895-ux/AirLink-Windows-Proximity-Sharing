import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from transfer_service import TransferReceiver, safe_filename


class TransferServiceTests(unittest.TestCase):
    def test_filename_is_sanitized(self):
        self.assertEqual(safe_filename(r"C:\\Users\\Alice\\hello.txt"), "hello.txt")
        self.assertNotIn("/", safe_filename("../../bad/name.txt"))

    def test_receiver_requires_approval_and_saves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            receiver = TransferReceiver(Path(tmp), port=0)
            port = receiver.server.server_address[1]
            receiver.start()
            base = f"http://127.0.0.1:{port}"
            data = b"real airlink test bytes\x00\x01"
            try:
                with urlopen(base + "/health", timeout=2) as r:
                    self.assertEqual(json.loads(r.read())['app'], 'AirLink')
                payload = json.dumps({"filename":"hello.txt", "size":len(data), "sender":"UnitTest"}).encode()
                req = Request(base + "/offer", data=payload, headers={"Content-Type":"application/json"}, method="POST")
                with urlopen(req, timeout=2) as r:
                    offer = json.loads(r.read())
                pending = receiver.next_pending()
                self.assertEqual(pending['id'], offer['id'])
                # Attempt upload before approval must be rejected.
                req = Request(base + "/upload/" + offer['id'], data=data, headers={"Content-Type":"application/octet-stream"}, method="POST")
                with self.assertRaises(HTTPError) as cm:
                    urlopen(req, timeout=2)
                self.assertEqual(cm.exception.code, 403)
                receiver.decide(offer['id'], True)
                req = Request(base + "/upload/" + offer['id'], data=data, headers={"Content-Type":"application/octet-stream"}, method="POST")
                with urlopen(req, timeout=2) as r:
                    result = json.loads(r.read())
                self.assertEqual(result['status'], 'complete')
                self.assertEqual(Path(result['saved_path']).read_bytes(), data)
            finally:
                receiver.stop()


if __name__ == '__main__':
    unittest.main()
