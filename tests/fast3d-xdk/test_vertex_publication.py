from pathlib import Path
import importlib
import unittest
import test_shade_cache as shade
import test_vertex_transform as vertex

class PublicationTests(unittest.TestCase):
    extra_includes=shade.ShadeCacheTests.extra_includes+'#include "fast3d/numeric.h"\n'
    @staticmethod
    def extra_projection(text):
        return importlib.import_module('vertex_publication_projection').transform(shade.ShadeCacheTests.extra_projection(text))
    extra_driver=staticmethod(shade.ShadeCacheTests.extra_driver)
    def test_full_vertex_publication(self):
        vertex.OUT.mkdir(parents=True,exist_ok=True)
        vertex.TransformTests.test_actual_vertex_composition(self)

if __name__=='__main__':unittest.main()
