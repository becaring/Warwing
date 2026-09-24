#include <cstdio>
#include <cstdlib>
#include <string>
#include <memory>
#include <stdexcept>
#include <stdint.h>
#if USE_STD
#include <variant>
#include <optional>
#define V std
#else
#include <xbox_compat/variant.h>
#include <xbox_compat/optional.h>
#define V xbox_compat
#endif
#if !defined(_XBOX)
#include "prism_shapes/processor.h"
#include "prism_shapes/gui.h"
#include "prism_shapes/lus.h"
#endif

static void check(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
struct Throwing {
    static int live; static bool failCopy,failMove,failAssign;
    int value;
    Throwing(int n=0):value(n) { ++live; }
    Throwing(const Throwing& o):value(o.value) { if(failCopy)throw std::runtime_error("copy"); ++live; }
    Throwing(Throwing&& o):value(o.value) { if(failMove)throw std::runtime_error("move"); o.value=-1; ++live; }
    Throwing& operator=(const Throwing& o) { if(failAssign)throw std::runtime_error("assign"); value=o.value;return *this; }
    Throwing& operator=(Throwing&& o) { if(failAssign)throw std::runtime_error("assign"); value=o.value;o.value=-1;return *this; }
    ~Throwing() { --live; }
};
int Throwing::live=0;bool Throwing::failCopy=false;bool Throwing::failMove=false;bool Throwing::failAssign=false;
struct SafeMove {
    static bool failCopy; int value;
    SafeMove(int n=0):value(n) {}
    SafeMove(const SafeMove& o):value(o.value) { if(failCopy)throw std::runtime_error("safe-copy"); }
    SafeMove(SafeMove&& o) throw():value(o.value) { o.value=-1; }
    SafeMove& operator=(const SafeMove& o) {value=o.value;return *this;}
    SafeMove& operator=(SafeMove&& o) throw() {value=o.value;o.value=-1;return *this;}
};bool SafeMove::failCopy=false;
#if !USE_STD
namespace xbox_compat { template<> struct is_nothrow_move<SafeMove> : std::true_type {}; }
#endif
struct Aligned { double values[8]; };
template<int N> struct Tag { int number; Tag(int n=0):number(n){} };
typedef V::variant<int,float,std::string,std::shared_ptr<int>,Tag<0>,Tag<1>,Tag<2>,Tag<3>,Tag<4>,Tag<5>,Tag<6>,Tag<7>,Tag<8>,Tag<9>,Tag<10>,Tag<11>,Tag<12>,Tag<13>,Tag<14> > Nineteen;

static int chooseUnsupportedLiteral(V::variant<int,float>) {return 1;}
static int chooseUnsupportedLiteral(std::string) {return 2;}
static void conversionParticipation(){
    check(chooseUnsupportedLiteral("literal")==2,"nonconvertible variant must not participate against string overload");
    check(chooseUnsupportedLiteral(7)==1,"valid variant integer conversion remains available");
    check(!std::is_convertible<const char*,V::variant<int,float> >::value,"unsupported pointer constructor excluded");
    check(std::is_convertible<const char*,V::variant<int,std::string> >::value,"supported string constructor retained");
    puts("conversion-participation-ok");
}

static void basic() {
    V::variant<int,float,std::string> a;
    check(a.index()==0 && V::get<int>(a)==0,"first alternative value initialized");
    a=true;check(a.index()==0 && V::get<int>(a)==1,"bool chooses int promotion");
    a=2.5f;check(V::get<float>(a)==2.5f,"exact float alternative");
    a="shader";check(a.index()==2 && V::get<std::string>(a)=="shader","literal selects string");
    bool caught=false;try{(void)V::get<int>(a);}catch(const V::bad_variant_access&){caught=true;}
    check(caught,"wrong type get throws");
    const V::variant<int,float,std::string>& ca=a;
    check(&V::get<std::string>(ca)==&V::get<std::string>(a),"const get identity");
    V::variant<int,float,std::string> b(a);a=5;
    check(V::get<std::string>(b)=="shader" && V::get<int>(a)==5,"copy and switch independently");
    b=b;check(V::get<std::string>(b)=="shader","self copy");
    Nineteen many=Tag<14>(314);
    check(many.index()==18 && V::get<Tag<14> >(many).number==314,"nineteenth alternative");
    Nineteen moved(std::move(many));check(V::get<Tag<14> >(moved).number==314,"move nineteenth");
    V::variant<int,Aligned> aligned=Aligned();
    uintptr_t start=(uintptr_t)&aligned,value=(uintptr_t)&V::get<Aligned>(aligned);
    check(value>=start && value+sizeof(Aligned)<=start+sizeof(aligned),"alternative lives inline");
    check(value % 8==0,"aligned inline storage");
    V::variant<bool,std::string> text="shader";
    check(text.index()==1 && V::get<std::string>(text)=="shader","pointer-to-bool narrowing excluded");
    puts("variant-basic-ok");
}
static void lifetime() {
    std::weak_ptr<int> weak;
    {
        std::shared_ptr<int> shared=std::make_shared<int>(42);weak=shared;
        V::variant<int,std::shared_ptr<int> > cache=nullptr;
        check(cache.index()==1 && !V::get<std::shared_ptr<int> >(cache),"null shared resource selection");
        cache=shared;shared.reset();
        V::variant<int,std::shared_ptr<int> > copy(cache);
        V::variant<int,std::shared_ptr<int> > moved(std::move(copy));
        check(copy.index()==1 && !V::get<std::shared_ptr<int> >(copy),"moved shared alternative stays active and empty");
        cache=3;check(*V::get<std::shared_ptr<int> >(moved)==42 && !weak.expired(),"shared lifetime after alternative switch");
    }
    check(weak.expired(),"all shared alternatives destroyed");puts("shared-lifetime-ok");
}
static void failure() {
    {
        V::variant<int,Throwing> source=Throwing(8),destination=7;
        Throwing::failMove=true;bool caught=false;
        try{destination=std::move(source);}catch(const std::runtime_error&){caught=true;}
        Throwing::failMove=false;
        check(caught && destination.valueless_by_exception(),"throwing type-changing move leaves valueless");
        check(destination.index()==V::variant_npos,"valueless discriminator");
        V::variant<int,Throwing> copiedEmpty(destination),assignedEmpty=9;
        assignedEmpty=destination;check(copiedEmpty.valueless_by_exception() && assignedEmpty.valueless_by_exception(),"copy valueless state");
        bool bad=false;try{(void)V::get<int>(destination);}catch(const V::bad_variant_access&){bad=true;}check(bad,"valueless get throws");
        destination=42;check(V::get<int>(destination)==42,"valueless recovery");
        Throwing::failCopy=true;caught=false;
        try{destination=source;}catch(const std::runtime_error&){caught=true;}
        Throwing::failCopy=false;check(caught && destination.valueless_by_exception(),"throwing copy with throwing move leaves valueless");
        destination=Throwing(9);Throwing::failAssign=true;caught=false;
        try{destination=source;}catch(const std::runtime_error&){caught=true;}
        Throwing::failAssign=false;check(caught && destination.index()==1 && V::get<Throwing>(destination).value==9,"same-type throwing assignment retains active type");
        Throwing::failCopy=true;caught=false;
        try{V::variant<int,Throwing> temporary(source);}catch(const std::runtime_error&){caught=true;}
        Throwing::failCopy=false;check(caught,"copy constructor propagates");
    }
    check(Throwing::live==0,"exactly one destructor per live alternative");
    {
        V::variant<int,SafeMove> old=91,source=SafeMove(2);SafeMove::failCopy=true;bool caught=false;
        try{old=source;}catch(const std::runtime_error&){caught=true;}
        SafeMove::failCopy=false;check(caught && old.index()==0 && V::get<int>(old)==91,"nothrow move preserves old value when copy throws");
    }
    puts("variant-failure-ok");
}
static void optionals() {
    V::optional<std::string> value;
    check(!value.has_value() && !value,"optional default empty");
    check(value.value_or("fallback")=="fallback","empty fallback literal");
    bool caught=false;try{(void)value.value();}catch(const V::bad_optional_access&){caught=true;}check(caught,"empty value throws");
    value="shader";check(value.has_value() && *value=="shader" && value->size()==6,"optional string assignment/access");
    V::optional<std::string> copy(value);value=V::nullopt;
    check(!value && copy.value()=="shader","optional copy/nullopt");
    V::optional<std::shared_ptr<int> > ptr(std::make_shared<int>(7));
    V::optional<std::shared_ptr<int> > moved(std::move(ptr));
    check(ptr.has_value() && !*ptr && **moved==7,"optional move leaves source engaged");
    copy.reset();check(!copy,"optional reset");
    {
        V::optional<Throwing> a,b(Throwing(2));Throwing::failCopy=true;caught=false;
        try{a=b;}catch(const std::runtime_error&){caught=true;}
        Throwing::failCopy=false;check(caught && !a,"throwing optional construction remains empty");
    }
    check(Throwing::live==0,"optional lifetime");puts("optional-ok");
}
#if !defined(_XBOX)
static void realShapes() {
    prism::ast::ASTTypes ast;
    check(V::holds_alternative<prism::ast::VariableNode>(ast),"real AST default");
    prism::ast::QuoteNode quote;quote.value="material";ast=quote;
    check(ast.index()==18 && V::get<prism::ast::QuoteNode>(ast).value=="material","actual AST nineteenth shape");
    prism::ContextTypes context=true;check(context.index()==1 && V::get<int>(context)==1,"actual Prism bool expression");
    prism::MTDArray<int> array;array.ptr=123;array.dimensions.push_back(5);context=array;
    prism::ContextTypes copied(context);check(V::get<prism::MTDArray<int> >(copied).dimensions[0]==5,"actual Prism vector ownership");
    prism::NodeType node=prism::TextNode{"body"};
    prism::NodeType moved(std::move(node));check(V::get<prism::TextNode>(moved).text=="body","actual rendering node shape");
    CVarVariant cvar=Color_RGBA8{1,2,3,4};
    check(cvar.index()==3 && V::get<Color_RGBA8>(cvar).a==4,"actual five-alternative GUI cvar");
    OptionsVariant options;
    check(options.index()==0 && !V::get<UIWidgets::ButtonOptions>(options).disabled,"actual GUI option default");
    UIWidgets::ComboboxOptions combo;combo.comboMap[3]="third";options=combo;
    check(options.index()==2 && V::get<UIWidgets::ComboboxOptions>(options).comboMap[3]==std::string("third"),"GUI derived exact alternative and map lifetime");
    options=UIWidgets::BtnSelectorOptions();check(options.index()==9,"actual tenth GUI option");
    lus_shapes::Reader reader;
    check(reader.index()==0 && !V::get<std::shared_ptr<tinyxml2::XMLDocument> >(reader),"actual File reader default");
    std::shared_ptr<int> owner=std::make_shared<int>(9);
    std::shared_ptr<Ship::BinaryReader> alias(owner,reinterpret_cast<Ship::BinaryReader*>(owner.get()));
    reader=alias;check(reader.index()==1 && V::get<std::shared_ptr<Ship::BinaryReader> >(reader)==alias,"actual File reader discriminator and pointer");
    lus_shapes::Cache cache=nullptr;check(cache.index()==1 && !V::get<std::shared_ptr<Ship::IResource> >(cache),"actual error/shared cache null selection");
    cache=lus_shapes::ResourceLoadError::NotFound;check(cache.index()==0 && V::get<lus_shapes::ResourceLoadError>(cache)==lus_shapes::ResourceLoadError::NotFound,"actual cache error alternative");
    puts("real-prism-gui-lus-shapes-ok");
}
#endif
int main(){try{conversionParticipation();basic();lifetime();failure();optionals();
#if !defined(_XBOX)
realShapes();
#endif
return 0;}catch(const std::exception&e){fprintf(stderr,"FAIL:%s\n",e.what());return 1;}}
