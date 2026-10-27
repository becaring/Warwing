"""Bind generated Smash projects to Shipyard's bounded XDK build contract."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve
PLATFORM_BASE = resolve(ROOT)
from xbox360_platform import parallel_build

OUT = ROOT / 'scratch/application-xdk/native'
PROJECT_DIR = ROOT / 'platform/xbox360'
NS = '{http://schemas.microsoft.com/developer/msbuild/2003}'
MSBUILD = Path('C:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe')
SDK = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')


def items(name):
    if name not in ('Smash360', 'Libultraship360'):
        raise ValueError('Unknown Xbox project: ' + name)
    return json.loads((OUT / 'project-items.json').read_text())[name]


def project_plan(name, jobs=8):
    project = PROJECT_DIR / (name + '.vcxproj')
    selected = items(name)
    elements = ET.parse(project).getroot().findall('.//' + NS + 'ClCompile[@Include]')
    if len(elements) != len(selected):
        raise ValueError('Smash project source count differs from inventory: ' + name)
    records = []
    for item, element in zip(selected, elements):
        if 'shipyard_source' in item:
            source = PLATFORM_BASE / item['shipyard_source']
            include = '$(ShipyardRoot)\\' + item['shipyard_source'].replace('/', '\\')
        else:
            source = OUT / 'source' / item['staged']
            include = '$(SmashSourceRoot)' + item['staged'].replace('/', '\\')
        if element.attrib['Include'] != include:
            raise ValueError('Smash project source order differs from inventory: ' + item['path'])
        obj = OUT / 'obj' / name / ('%s_%s.obj' % (Path(item['path']).stem,
                                          hashlib.sha256(item['path'].encode()).hexdigest()[:16]))
        records.append(dict(include=include, source=str(source), object=str(obj), sha256=item['sha256']))
    return parallel_build.plan(project, records, OUT/'parallel'/name, jobs)


def build_project(name, jobs=8, full_profiling=False, rebuild=False):
    planned = project_plan(name, jobs)
    if rebuild:
        owned = (OUT/'obj'/name).resolve()
        for row in planned.sources:
            if row.object.parent.resolve() != owned:
                raise ValueError('Object outside owned project directory: ' + str(row.object))
            if row.object.exists():
                row.object.unlink()
    args = ['/p:Configuration=Release', '/p:Platform=Xbox 360',
            '/p:PlatformToolset=2010-01', '/p:TargetPlatformSdkPath=' + str(SDK),
            '/p:VCTargetsPath=C:/Program Files (x86)/MSBuild/Microsoft.Cpp/v4.0',
            '/p:SmashFullProfiling=' + str(int(full_profiling)),
            '/p:ShipyardRoot=' + str(PLATFORM_BASE), '/nologo', '/verbosity:minimal']
    receipt_path = planned.output/'compile-receipt.json'
    try:
        receipt = parallel_build.run(planned, [str(MSBUILD)], arguments=args,
                                     owned_roots=[ROOT, PLATFORM_BASE])
        for index, shard in enumerate(receipt['builds']):
            print('%s shard %02d/%02d: exit %s in %.1fs' %
                  (name, index+1, len(receipt['builds']), shard['exit'], shard['seconds']), flush=True)
        if receipt['build_exit']:
            return receipt['build_exit']
        view = parallel_build.plan_link_view(planned, receipt)
        parallel_build.write_link_view(view)
        link_log = planned.output/'link.log'
        command = [str(MSBUILD), str(view.project), '/t:Build',
                   '/p:BuildProjectReferences=false', *args]
        try:
            with link_log.open('w', encoding='utf-8') as output:
                result = subprocess.run(command, cwd=PROJECT_DIR,
                                        stdout=output, stderr=subprocess.STDOUT)
        finally:
            parallel_build.remove_link_view(view)
        if result.returncode:
            print('%s link failed; see %s' % (name, link_log), flush=True)
            return result.returncode
        parallel_build.verify_receipt(planned, receipt)
        output = OUT/'build'/ (name + ('.lib' if name == 'Libultraship360' else '.xex'))
        if not output.is_file():
            raise ValueError('XDK build did not produce ' + str(output))
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        (planned.output/'link-receipt.json').write_text(json.dumps({
            'project':name, 'command':command, 'compile_receipt':str(receipt_path),
            'output':str(output), 'output_sha256':digest, 'exit':result.returncode,
        }, indent=2) + '\n', encoding='utf-8')
        print('%s linked: %s' % (name, digest), flush=True)
        return 0
    finally:
        parallel_build.remove_shards(planned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', choices=('Libultraship360', 'Smash360'), required=True)
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--full-profiling', action='store_true')
    args = parser.parse_args()
    if args.build:
        projects = ('Libultraship360', 'Smash360') if args.project == 'Smash360' else (args.project,)
        for name in projects:
            result = build_project(name, args.jobs, args.full_profiling, args.rebuild)
            if result:
                return result
        return 0
    planned = project_plan(args.project, args.jobs)
    print('%s: %d sources in %d Shipyard shards' %
          (args.project, len(planned.sources), len(planned.shards)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
