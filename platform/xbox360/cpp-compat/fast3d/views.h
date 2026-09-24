#ifndef SMASH360_FAST3D_VIEWS_H
#define SMASH360_FAST3D_VIEWS_H
#include <cstddef>
#include <cstring>
#include <string>
#include <stdexcept>
#include <vector>

namespace Smash360Fast3D {
// Dynamic-extent span surface used by Interpreter::PrewarmShaders. Non-owning;
// callers retain the same bounds and lifetime obligations as std::span.
template<class T> class span {
    T* pointer_;size_t length_;
public:
    span():pointer_(nullptr),length_(0){}
    span(T* pointer,size_t length):pointer_(pointer),length_(length){}
    template<size_t N> span(T (&array)[N]):pointer_(array),length_(N){}
    template<class U> span(std::vector<U>& values):pointer_(values.data()),length_(values.size()){}
    template<class U> span(const std::vector<U>& values):pointer_(values.data()),length_(values.size()){}
    size_t size()const{return length_;}
    bool empty()const{return length_==0;}
    T* data()const{return pointer_;}
    T& operator[](size_t index)const{return pointer_[index];}
    T* begin()const{return pointer_;}
    T* end()const{return length_?pointer_+length_:pointer_;}
};

class string_view {
    const char* pointer_;size_t length_;
public:
    string_view():pointer_(nullptr),length_(0){}
    string_view(const char* value):pointer_(value),length_(std::strlen(value)){}
    string_view(const char* value,size_t length):pointer_(value),length_(length){}
    string_view(const std::string& value):pointer_(value.data()),length_(value.size()){}
    size_t size()const{return length_;}
    size_t length()const{return length_;}
    bool empty()const{return length_==0;}
    const char* data()const{return pointer_;}
    const char* begin()const{return pointer_;}
    const char* end()const{return length_?pointer_+length_:pointer_;}
    bool starts_with(string_view prefix)const{
        return prefix.length_<=length_&&(!prefix.length_||std::memcmp(pointer_,prefix.pointer_,prefix.length_)==0);
    }
    string_view substr(size_t position,size_t count=static_cast<size_t>(-1))const{
        if(position>length_)throw std::out_of_range("string_view::substr");
        size_t remainder=length_-position;
        return string_view(position?pointer_+position:pointer_,count<remainder?count:remainder);
    }
    int compare(string_view other)const{
        size_t common=length_<other.length_?length_:other.length_;
        int result=common?std::memcmp(pointer_,other.pointer_,common):0;
        return result?result:length_<other.length_?-1:length_>other.length_?1:0;
    }
    std::string str()const{return length_?std::string(pointer_,length_):std::string();}
};
// XDK's std::map lacks transparent find. Preserve non-owning lookup and avoid
// introducing temporary-string allocation; the bounded texture registry is
// walked in its existing key order. No insertion or comparator-state change.
template<class Map> typename Map::iterator FindStringView(Map& map,string_view key){
    typename Map::iterator it=map.begin();
    for(;it!=map.end();++it){int order=string_view(it->first).compare(key);if(order==0)return it;if(order>0)break;}
    return map.end();
}
template<class Map> typename Map::const_iterator FindStringView(const Map& map,string_view key){
    typename Map::const_iterator it=map.begin();
    for(;it!=map.end();++it){int order=string_view(it->first).compare(key);if(order==0)return it;if(order>0)break;}
    return map.end();
}
template<class T> const T& Clamp(const T& value,const T& low,const T& high){return value<low?low:high<value?high:value;}
}
#endif
