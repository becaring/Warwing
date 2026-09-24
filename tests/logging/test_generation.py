"""Pinned input rejection and deterministic output/provenance checks."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'scratch/logging-xdk'
sys.dont_write_bytecode=True
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def snapshot():
    return {str(p.relative_to(OUT)):sha(p) for folder in ('include','core-include') for p in sorted((OUT/folder).rglob('*')) if p.is_file()}
def main():
    command=[sys.executable,str(ROOT/'tools/prepare_logging_xdk.py')]
    subprocess.run(command,check=True);before=snapshot()
    subprocess.run(command,check=True);assert before==snapshot(),'Generation is not deterministic'
    for folder,name in [('include','logging-manifest.json'),('core-include','logging-core-manifest.json')]:
        report=json.loads((OUT/folder/name).read_text())
        for entry in report['sources']:
            generated=OUT/folder/entry['path'];original=ROOT/'upstream/dependencies/spdlog/include'/entry['path']
            assert sha(generated)==entry['output_sha256']
            assert sha(original)==entry['source_sha256']
            assert original.as_posix() in generated.read_text()
    spec=importlib.util.spec_from_file_location('generation_check',ROOT/'platform/xbox360/cpp-compat/logging/generate_core.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fake=OUT/'generation-test-input';(fake/'spdlog').mkdir(parents=True,exist_ok=True)
    (fake/'spdlog/common.h').write_text('// deliberately changed input\n')
    module.UP=fake
    try:module.common()
    except ValueError as error:assert 'core source changed common.h' in str(error)
    else:raise AssertionError('Changed upstream source was accepted')
    print('PASS deterministic generation, exact source/output hashes, line provenance, and changed-input rejection')
if __name__=='__main__':main()
