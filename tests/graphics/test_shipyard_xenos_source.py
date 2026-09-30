"""The application compiles the physical Shipyard renderer, not a projection."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)


class ShipyardXenosSourceTests(unittest.TestCase):
    def test_project_uses_physical_core_and_narrow_adapter(self):
        items=json.loads((ROOT/'scratch/application-xdk/native/project-items.json').read_text())['Smash360']
        by_path={item['path']:item for item in items}
        core='shipyard/sources/xenos/core.cpp'
        cache='shipyard/sources/xenos/shader_cache.cpp'
        self.assertIn(core,by_path)
        self.assertEqual(by_path[core]['shipyard_source'],'sources/xenos/core.cpp')
        self.assertIn(cache,by_path)
        self.assertEqual(by_path[cache]['shipyard_source'],'sources/xenos/shader_cache.cpp')
        surface='shipyard/sources/presentation/xenos_surface.cpp'
        self.assertIn(surface,by_path)
        self.assertEqual(by_path[surface]['shipyard_source'],'sources/presentation/xenos_surface.cpp')
        provider='shipyard/sources/graphics/shader_provider.cpp'
        self.assertIn(provider,by_path)
        self.assertEqual(by_path[provider]['shipyard_source'],'sources/graphics/shader_provider.cpp')
        self.assertIn('platform/xbox360/graphics/api.cpp',by_path)
        self.assertIn('platform/xbox360/graphics/shipyard_services.cpp',by_path)
        self.assertIn('platform/xbox360/graphics/shader_cache_adapter.cpp',by_path)
        self.assertNotIn('scratch/graphics-xdk/gfx_xenos.cpp',by_path)
        self.assertNotIn('scratch/graphics-xdk/shader_cache.cpp',by_path)
        self.assertFalse((ROOT/'scratch/graphics-xdk/gfx_xenos.cpp').exists())
        self.assertFalse((ROOT/'scratch/graphics-xdk/shader_cache.cpp').exists())
        self.assertFalse((ROOT/'scratch/graphics-xdk/include/shader_cache.h').exists())
        self.assertFalse((ROOT/'scratch/graphics-xdk/include/window_pacing.inc').exists())
        self.assertFalse((ROOT/'platform/xbox360/graphics/donor/platform.cpp').exists())
        project=(ROOT/'platform/xbox360/Smash360.vcxproj').read_text()
        self.assertIn('$(ShipyardRoot)\\sources\\xenos\\core.cpp',project)
        self.assertIn('$(ShipyardRoot)\\sources\\xenos\\shader_cache.cpp',project)
        self.assertIn('$(ShipyardRoot)\\sources\\presentation\\xenos_surface.cpp',project)
        self.assertIn('$(ShipyardRoot)\\sources\\graphics\\shader_provider.cpp',project)
        self.assertNotIn('scratch\\graphics-xdk\\gfx_xenos.cpp',project)
        self.assertNotIn('scratch\\graphics-xdk\\shader_cache.cpp',project)
        adapter=(ROOT/'platform/xbox360/graphics/api.cpp').read_text()
        source=SHIPYARD_BASE / 'sources/xenos/core.cpp'
        self.assertIn('Shipyard::Xenos::LoadShaderCode,Shipyard::Xenos::StoreShaderCode',adapter)
        self.assertIn('ShipyardXenos::SetShaderCache(&cache)',adapter)
        core_text=''.join(source.read_text().split())
        self.assertIn('if(shader_cache_ops.load)',core_text)
        self.assertIn('if(shader_cache_ops.store)',core_text)
        window=(ROOT/'platform/xbox360/graphics/window_xenos.cpp').read_text()
        self.assertIn('mSurface.Prepare(',window)
        self.assertNotIn('ApplyXenosPresentationInterval(',window)
        self.assertNotIn('mPacing.Next()',window)
        self.assertNotIn('window_pacing.inc',window)


if __name__=='__main__':unittest.main()
