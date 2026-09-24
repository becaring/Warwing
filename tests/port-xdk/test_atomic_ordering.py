"""Inspect exact PPC fences in each production atomic-load probe, not a file-wide grep."""
from pathlib import Path
import subprocess
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
class AtomicOrderingTest(unittest.TestCase):
    def test_xdk_load_fences(self):
        out=ROOT/'scratch/port-xdk/atomic-ordering';out.mkdir(parents=True,exist_ok=True)
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        obj=out/'probe.obj'
        command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/O2','/Ob2','/MT','/EHsc','/D_XBOX','/DNOMINMAX','/I'+str(ROOT.parent/'LibUltraShip+Fast3D360/sources'),'/I'+str(sdk/'include/xbox'),'/Fo'+str(obj),str(Path(__file__).with_name('atomic_ordering_probe.cpp'))]
        run=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        run=subprocess.run([str(sdk/'bin/win32/dumpbin.exe'),'/disasm',str(obj)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        (out/'probe.asm').write_text(run.stdout)
        block=re.search(r'(?m)^ReadFastRelaxed:\s*\n(.*?)(?=^\S|\Z)',run.stdout,re.S|re.M)
        self.assertIsNotNone(block)
        ops=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)',block[1])
        self.assertEqual(ops,['lwz','blr'],'relaxed diagnostic read must not reserve/write the cache line')
        for name,width in [('ReadAcquire64',64),('ReadAcquire32',32),('ReadSeq64',64),('ReadSeq32',32)]:
            block=re.search(r'(?m)^'+name+r':\s*\n(.*?)(?=^\S|\Z)',run.stdout,re.S|re.M)
            self.assertIsNotNone(block,name+' not found')
            instructions=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+([0-9A-Fa-f]{8})\s+(\S+)',block[1])
            words=[x[0].upper() for x in instructions];ops=[x[1] for x in instructions]
            if 'Acquire' in name:
                # A naturally aligned native load is atomic on Xenon. Acquire
                # must not take a reservation, write the value back, mask
                # interrupts, or call a helper just to read the generation.
                native_load='ld' if width==64 else 'lwz'
                self.assertEqual(ops.count(native_load),1,name+' needs one native-width read')
                self.assertEqual(words.count('7C2004AC'),1,name+' needs one post-read acquire fence')
                self.assertLess(ops.index(native_load),words.index('7C2004AC'),name)
                self.assertEqual(ops[-1],'blr',name)
                self.assertEqual([op for op in ops if op.startswith('b')],['blr'],
                                 name+' acquire must be unconditional on every return path')
                for forbidden in ('ldarx','lwarx','stdcx.','stwcx.','mfmsr','mtmsree','bl','b','std','stw'):
                    self.assertNotIn(forbidden,ops,name)
                self.assertEqual(words.count('7C0004AC'),0,name+' must not retain redundant full barriers')
                continue
            self.assertIn('ldarx' if width==64 else 'lwarx',ops,name)
            self.assertIn('stdcx.' if width==64 else 'stwcx.',ops,name)
            # XDK duplicates return tails across successful/mismatched CAS paths.
            # Check every CFG return and reservation retry, not static totals.
            decoded={int(a,16):(word.upper(),op,args.strip()) for a,word,op,args in re.findall(r'(?m)^\s*([0-9A-Fa-f]+):\s+([0-9A-Fa-f]{8})\s+(\S+)[ \t]*(.*)$',block[1])}
            pending=[(min(decoded),0,0,False)];seen=set();returns=0
            while pending:
                state=pending.pop()
                if state in seen:continue
                seen.add(state);pc,light,full,stored=state
                self.assertIn(pc,decoded,name+' escaped probe')
                word,op,args=decoded[pc]
                if op in ('ldarx','lwarx'):stored=False
                if op in ('stdcx.','stwcx.'):stored=True
                if word=='7C2004AC':
                    self.assertTrue(stored,name+' acquire barrier precedes atomic read');light+=1
                if word=='7C0004AC':full+=1
                self.assertLessEqual(light+full,2,name+' repeated fences on a path')
                if op=='blr':
                    self.assertTrue(stored,name+' return without atomic operation')
                    self.assertEqual((light,full),(1,0) if 'Acquire' in name else (0,2),name)
                    returns+=1;continue
                if op.startswith('b'):
                    target=args.split(',')[-1].split(';')[0].strip()
                    dest=min(decoded) if target==name else int(target,16)
                    pending.append((dest,light,full,stored))
                    if op=='b':continue
                pending.append((pc+4,light,full,stored))
            self.assertGreater(returns,0,name)

        # These consumers have ordinary nonvolatile data accesses following the
        # atomic read. Verify compiler ordering as well as the hardware fence.
        for name,width in [('AcquireObserve64',64),('AcquireObserve32',32)]:
            block=re.search(r'(?m)^'+name+r':\s*\n(.*?)(?=^\S|\Z)',run.stdout,re.S|re.M)
            self.assertIsNotNone(block,name+' not found')
            instructions=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+([0-9A-Fa-f]{8})\s+(\S+)[ \t]*(.*)$',block[1])
            words=[v[0].upper() for v in instructions]
            barrier=words.index('7C2004AC')
            generation=[i for i,(_,op,args) in enumerate(instructions)
                        if op==('ld' if width==64 else 'lwz') and args.endswith(',0(r3)')]
            payload=[i for i,(_,op,args) in enumerate(instructions) if op=='lwz' and args.endswith(',0(r4)')]
            result=[i for i,(_,op,args) in enumerate(instructions) if op=='stw' and args.endswith(',0(r5)')]
            self.assertEqual(len(generation),1,name+' generation load missing')
            self.assertEqual(len(payload),1,name+' ordinary payload load missing')
            self.assertEqual(len(result),1,name+' ordinary result store missing')
            self.assertLess(generation[0],barrier,name)
            self.assertGreater(payload[0],barrier,name+' compiler moved payload ahead of acquire')
            self.assertGreater(result[0],barrier,name+' compiler moved store ahead of acquire')

if __name__=='__main__':unittest.main()
