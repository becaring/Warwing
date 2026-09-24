"""Actual complete vertex path under all four host rounding modes.

Tests the projected production predicate: nonnearest batches never enter VMX.
Native FPSCR reader instruction evidence lives in test_light_batch.py.
"""
import unittest
import test_vertex_publication as publication
import test_vertex_transform as vertex


class RoundingTests(unittest.TestCase):
    extra_includes=publication.PublicationTests.extra_includes+r'''
#include "fast3d/vertex_transform.h"
#include <cstdlib>
static unsigned observedVmx;
static bool ObservedTransformPositions(const void* vertices,size_t count,const float matrix[4][4],void* output) {
    if(!Shipyard::Fast3D::NearestRounding())std::abort();
    ++observedVmx;
    return Shipyard::Fast3D::TransformPositions(vertices,count,matrix,output);
}
'''
    @staticmethod
    def extra_projection(text):
        text=publication.PublicationTests.extra_projection(text)
        return text.replace('Shipyard::Fast3D::TransformPositions(vertices,n_vertices,mRsp->MP_matrix,xboxTransformed)',
                            'ObservedTransformPositions(vertices,n_vertices,mRsp->MP_matrix,xboxTransformed)')
    @staticmethod
    def extra_driver(text):
        text=publication.PublicationTests.extra_driver(text)
        text=text.replace('int main() {','int DriverMain() {')
        return text+r'''
int main() {
    const unsigned modes[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    const unsigned saved=_controlfp(0,0)&_MCW_RC;
    for(unsigned i=0;i<4;++i) {
        _controlfp(modes[i],_MCW_RC);
        observedVmx=0;
        if(DriverMain())return 1;
        require(i==0?observedVmx>0:observedVmx==0,"VMX nearest predicate was bypassed");
    }
    _controlfp(saved,_MCW_RC);
    puts("PASS actual original/projected full vertex paths in all four rounding modes; nonnearest never enters VMX");
}
'''
    def test_four_rounding_modes(self):
        vertex.OUT.mkdir(parents=True,exist_ok=True)
        vertex.TransformTests.test_actual_vertex_composition(self)


if __name__=='__main__':unittest.main()
