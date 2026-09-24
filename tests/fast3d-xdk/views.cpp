#include "fast3d/views.h"
#include "atomic/atomic.h"
#include <map>
#include <stdexcept>
#if !defined(_XBOX)
#include <span>
#include <string_view>
#endif
static void require(bool value){if(!value)throw std::runtime_error("Fast3D compatibility contract failed");}
int main(){
    char bytes[]={'a','l','t','/','x','\0','y'};
    Smash360Fast3D::string_view view(bytes,7);
    require(view.starts_with("alt/")&&view.substr(4).size()==3&&view.substr(4).data()==bytes+4);
    bytes[4]='z';require(view.substr(4).str()==std::string("z\0y",3));
    require(view.substr(7).empty());
    bool failed=false;try{view.substr(8);}catch(const std::out_of_range&){failed=true;}require(failed);
    Smash360Fast3D::string_view empty;require(empty.empty()&&empty.starts_with(empty)&&empty.substr(0).empty());
    std::map<std::string,int> names;names["a"]=1;names[std::string("z\0y",3)]=2;
    require(Smash360Fast3D::FindStringView(names,view.substr(4))->second==2);
    require(Smash360Fast3D::FindStringView(names,"absent")==names.end());
    const std::map<std::string,int>& constNames=names;
    require(Smash360Fast3D::FindStringView(constNames,"a")->second==1);
    int array[]={2,4,6};Smash360Fast3D::span<int> span(array);
    span[1]=9;require(array[1]==9&&span.size()==3&&span.data()==array&&span.end()==array+3);
    std::vector<int> vector(4,7);Smash360Fast3D::span<const int> vectorView(vector);
    require(vectorView.size()==4&&vectorView[3]==7&&vectorView.data()==vector.data());
    Shipyard::Atomic::atomic<int,Shipyard::Atomic::native_relaxed_counter> counter(2);int expected=1;
    require(!counter.compare_exchange_weak(expected,0,Shipyard::Atomic::memory_order_relaxed)&&expected==2);
    require(counter.compare_exchange_weak(expected,3,Shipyard::Atomic::memory_order_relaxed));
    counter.store(4,Shipyard::Atomic::memory_order_relaxed);require(counter.load(Shipyard::Atomic::memory_order_relaxed)==4);
#if !defined(_XBOX)
    std::string_view original(bytes,7);
    require(original.starts_with("alt/")==view.starts_with("alt/"));
    require(original.substr(4)==view.substr(4).str());
    std::span<int> originalSpan(array);require(originalSpan.data()==span.data()&&originalSpan.size()==span.size());
#endif
    return 0;
}
