"""Compare projected synchronous loads with the pinned cache and async policy."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(source, signature):
    first = source.index(signature)
    return source[first : source.index("\n}", first) + 2]


class SynchronousCacheTests(unittest.TestCase):
    def test_selected_cache_hits_avoid_future_allocation(self):
        source = (ROOT / "scratch/resources-xdk/generated/src/ship/resource/ResourceManager.cpp").read_text()
        source = "\n".join(line for line in source.splitlines() if not line.startswith("#line"))
        signatures = [
            "std::shared_ptr<IResource> ResourceManager::LoadResource(const ResourceIdentifier&",
            "xbox_compat::variant<ResourceManager::ResourceLoadError, std::shared_ptr<IResource>>\nResourceManager::CheckCache(const ResourceIdentifier&",
            "std::shared_ptr<IResource> ResourceManager::GetCachedResource(const ResourceIdentifier&",
            "std::shared_ptr<IResource>\nResourceManager::GetCachedResource(xbox_compat::variant",
        ]
        selected = "\n".join(method(source, signature) for signature in signatures)
        driver = (
            """\

#include <cassert>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <tuple>
#include <variant>
#define SPDLOG_TRACE(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
namespace xbox_compat = std;
namespace Shipyard { namespace Async { using mutex=std::mutex; \
template<class T> using lock_guard=std::lock_guard<T>; } }
namespace BS { namespace pr { const int highest=1; } }
struct IResource { bool dirty=false; bool IsDirty() const { return \
dirty; } static const std::string gAltAssetPrefix; };
const std::string IResource::gAltAssetPrefix=\"alt/\";
struct ResourceInitData {};
struct ResourceIdentifier {
    std::string Path; uintptr_t Owner; int Parent;
    ResourceIdentifier(std::string p,uintptr_t o=0,int \
parent=0):Path(p),Owner(o),Parent(parent){}
    bool operator<(const ResourceIdentifier& b)const { return \
std::tie(Path,Owner,Parent)<std::tie(b.Path,b.Owner,b.Parent); }
};
bool OtrSignatureCheck(const char* p) { return std::strncmp(p,\
\"__OTR__\",7)==0; }
struct ResourceManager {
    enum class ResourceLoadError { NotCached, NotFound };
    using Line=std::variant<ResourceLoadError,std::shared_ptr<IResource>>;
    std::map<ResourceIdentifier,Line> mResourceCache;
    std::mutex mMutex; bool mAltAssetsEnabled=false;
    int promises=0,queued=0,normalized=0; \
std::shared_ptr<ResourceInitData> lastInit;
    std::shared_ptr<IResource> loaded=std::make_shared<IResource>();
    Line CheckCache(const ResourceIdentifier&,bool);
    std::shared_ptr<IResource> GetCachedResource(const \
ResourceIdentifier&,bool);
    std::shared_ptr<IResource> GetCachedResource(Line);
    std::shared_ptr<IResource> LoadResource(const ResourceIdentifier&,\
bool,std::shared_ptr<ResourceInitData>);
    struct Future { std::shared_ptr<IResource> value; \
std::shared_ptr<IResource> get(){return value;} };
    Future LoadResourceAsync(const ResourceIdentifier& id,bool exact,\
int priority,std::shared_ptr<ResourceInitData> init=nullptr) {
        if(OtrSignatureCheck(id.Path.c_str())) { ++normalized; return \
LoadResourceAsync(ResourceIdentifier(id.Path.substr(7),id.Owner,\
id.Parent),exact,priority); }
        auto hit=GetCachedResource(id,exact);
        if(hit) { ++promises; return {hit}; }
        ++queued; lastInit=init; return {loaded};
    }
    std::shared_ptr<IResource> Original(const ResourceIdentifier& id,\
bool exact,std::shared_ptr<ResourceInitData> init) {
        return LoadResourceAsync(id,exact,BS::pr::highest,init).get();
    }
};
"""
            + selected
            + r"""
int main() {
    ResourceManager m;
    auto base=std::make_shared<IResource>(),alt=std::make_shared<IResource>(),dirty=std::make_shared<IResource>();
    dirty->dirty=true;
    auto init=std::make_shared<ResourceInitData>();
    auto check=[&](ResourceIdentifier id,bool exact,bool bypass) {
        auto expected=m.Original(id,exact,init);
        m.promises=m.queued=m.normalized=0; m.lastInit.reset();
        assert(m.LoadResource(id,exact,init)==expected);
        if(bypass) assert(m.promises==0 && m.queued==0);
    };
    m.mResourceCache[ResourceIdentifier("a")]=base;
    check(ResourceIdentifier("a"),false,true);
    m.mAltAssetsEnabled=true;
    check(ResourceIdentifier("a"),false,true); // alternate absent
    m.mResourceCache[ResourceIdentifier("alt/a")]=ResourceManager::ResourceLoadError::NotCached;
    check(ResourceIdentifier("a"),false,true);
    m.mResourceCache[ResourceIdentifier("alt/a")]=ResourceManager::ResourceLoadError::NotFound;
    check(ResourceIdentifier("a"),false,true);
    m.mResourceCache[ResourceIdentifier("alt/a")]=alt;
    check(ResourceIdentifier("a"),false,true);
    check(ResourceIdentifier("a"),true,true);
    m.mResourceCache[ResourceIdentifier("alt/a")]=dirty;
    check(ResourceIdentifier("a"),false,false); assert(m.queued==1 && m.lastInit==init);
    m.mResourceCache[ResourceIdentifier("alt/a")]=std::shared_ptr<IResource>();
    check(ResourceIdentifier("a"),false,false); assert(m.queued==1);
    m.mAltAssetsEnabled=false; m.mResourceCache[ResourceIdentifier("a")]=dirty;
    check(ResourceIdentifier("a"),false,false); assert(m.queued==1);
    m.mResourceCache[ResourceIdentifier("a")]=base;
    check(ResourceIdentifier("a",1),false,false); assert(m.queued==1);
    check(ResourceIdentifier("a",0,1),false,false); assert(m.queued==1);
    check(ResourceIdentifier("__OTR__a"),false,true); assert(m.normalized==0 && m.promises==0);
    check(ResourceIdentifier("__OTR____OTR__a"),false,true);
    m.mResourceCache[ResourceIdentifier("a",7,9)]=alt;
    check(ResourceIdentifier("__OTR__a",7,9),true,true);
    check(ResourceIdentifier("__OTR__missing"),true,false);
    assert(m.queued==1 && m.normalized==1 && !m.lastInit);
    m.mResourceCache[ResourceIdentifier("a")]=dirty;
    check(ResourceIdentifier("__OTR__a"),true,false);
    assert(m.queued==1 && m.normalized==1 && !m.lastInit);
    check(ResourceIdentifier("missing"),false,false); assert(m.queued==1 && m.lastInit==init);
}
"""
        )
        vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
        installation = subprocess.check_output(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            text=True,
        ).strip()
        with tempfile.TemporaryDirectory(prefix="smash-sync-cache-") as folder:
            out = Path(folder)
            (out / "contract.cpp").write_text(driver)
            batch = out / "compile.cmd"
            batch.write_text(
                '@echo off\ncall "' + installation + '/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
                "if errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /EHsc /MT contract.cpp /Fecontract.exe\nexit /b %errorlevel%\n"
            )
            built = subprocess.run(
                [os.environ["ComSpec"], "/d", "/c", str(batch)], cwd=out, capture_output=True, text=True
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(out / "contract.exe")], capture_output=True, text=True, timeout=15)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
