from pathlib import Path
import unittest,subprocess,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
class OverlayTests(unittest.TestCase):
    def test_pinned_and_deterministic(self):
        script=ROOT/'tools/prepare_input_xdk.py';out=ROOT/'scratch/input-xdk/source'
        subprocess.run(['C:/Python313/python.exe',str(script)],check=True,capture_output=True)
        before={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        subprocess.run(['C:/Python313/python.exe',str(script)],check=True,capture_output=True)
        after={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        for entry in json.loads(before['input-manifest.json'])['sources']:
            source=ROOT/'upstream/BattleShip'/entry['path']
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),entry['source_sha256'])
            self.assertEqual(hashlib.sha256(before[entry['path']]).hexdigest(),entry['output_sha256'])
        self.assertFalse((out/'SDL.h').exists())
if __name__=='__main__':unittest.main()
