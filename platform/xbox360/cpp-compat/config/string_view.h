#ifndef SMASH360_CONFIG_STRING_VIEW_H
#define SMASH360_CONFIG_STRING_VIEW_H
#include <string>
#include <cstring>
#include <functional>
#include <stdexcept>
#if !defined(_XBOX)
#include <string_view>
#endif
namespace xbox_compat {
class string_view {
public:
    typedef const char* const_iterator;
    static const size_t npos=static_cast<size_t>(-1);
    string_view():data_(0),size_(0){}
    string_view(const char* value):data_(value),size_(std::strlen(value)){}
    string_view(const char* value,size_t length):data_(value),size_(length){}
    string_view(const std::string& value):data_(value.data()),size_(value.size()){}
    const char* data()const{return data_;} size_t size()const{return size_;} size_t length()const{return size_;}
    bool empty()const{return size_==0;} const char& operator[](size_t i)const{return data_[i];}
    const_iterator begin()const{return data_;}const_iterator end()const{return size_?data_+size_:data_;}
    string_view substr(size_t pos=0,size_t count=npos)const{if(pos>size_)throw std::out_of_range("string_view::substr");size_t remaining=size_-pos;return string_view(pos?data_+pos:data_,count<remaining?count:remaining);}
    size_t find(string_view value,size_t pos=0)const{if(pos>size_||value.size_>size_-pos)return npos;if(!value.size_)return pos;for(size_t i=pos;i<=size_-value.size_;++i)if(std::memcmp(data_+i,value.data_,value.size_)==0)return i;return npos;}
    size_t rfind(char value,size_t pos=npos)const{if(!size_)return npos;size_t i=pos<size_?pos:size_-1;do{if(data_[i]==value)return i;}while(i--!=0);return npos;}
    size_t find_last_of(string_view values,size_t pos=npos)const{if(!size_||values.empty())return npos;size_t i=pos<size_?pos:size_-1;do{for(size_t j=0;j<values.size();++j)if(data_[i]==values[j])return i;}while(i--!=0);return npos;}
private:const char* data_;size_t size_;
};
inline bool operator==(string_view a,string_view b){return a.size()==b.size()&&(!a.size()||std::memcmp(a.data(),b.data(),a.size())==0);}
inline bool operator!=(string_view a,string_view b){return !(a==b);}
inline size_t hash_string_view(string_view value){
#if defined(_XBOX)
    // Same allocation-free hash as XDK xfunctional::hash<std::string>.
    // The view and owning-key hashes must match for map equality/lookup.
    size_t hash=2166136261U;const size_t stride=1+value.size()/10;
    for(size_t i=0;i<value.size();i+=stride)hash=16777619U*hash^static_cast<size_t>(value[i]);
    return hash;
#else
    return std::hash<std::string_view>()(std::string_view(value.data(),value.size()));
#endif
}
}
#endif
